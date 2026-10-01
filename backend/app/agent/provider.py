"""LLM provider abstraction (Phase 4). OpenAI-compatible interface with
replaceable implementations. Secrets stay in environment variables and are
never logged, stored, or sent to the frontend."""

import os
from typing import Any


class ProviderUnavailable(Exception):
    """Raised when no usable LLM provider is configured or reachable."""


class ProviderFailure(Exception):
    """Raised when the provider call fails at runtime."""


class LLMProvider:
    name = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def describe(self) -> dict:
        raise NotImplementedError

    def complete_json(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        """Return a parsed JSON object for the given chat messages."""
        raise NotImplementedError


class DeterministicProvider(LLMProvider):
    """Offline narrator used when no LLM key is configured.

    Produces fixed template wording only. It never invents facts: decision
    selection stays in the deterministic orchestrator + guardrails, and all
    financial values come from backend tools.
    """

    name = "deterministic"

    def is_available(self) -> bool:
        return True

    def describe(self) -> dict:
        return {"provider": self.name, "model": "template-narrator-v1"}

    def complete_json(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        if purpose == "narration":
            return {
                "reasoningSummary": (
                    "Based on the uploaded records, reconciliation indicates the position "
                    "stated below. Supporting evidence available is listed with its source "
                    "references. Review required before submission."
                )
            }
        if purpose == "draft_prose":
            return {
                "explanation": (
                    "Based on the uploaded records, the reconciliation indicates the explained "
                    "and unexplained amounts stated in this draft. The findings below reference "
                    "the underlying return rows and source documents."
                )
            }
        if purpose == "decision_proposal":
            # The deterministic provider abstains: orchestrator falls back to the
            # guardrail-constrained default decision.
            return {"decision": "ABSTAIN", "reasoningSummary": ""}
        raise ProviderFailure(f"Unknown purpose '{purpose}' for deterministic provider.")


class OpenAICompatibleProvider(LLMProvider):
    """Minimal OpenAI-compatible chat-completions client (vendor-neutral)."""

    name = "openai-compatible"

    def __init__(self) -> None:
        import httpx  # local import: keeps module importable without httpx

        self._httpx = httpx
        self.base_url = (os.environ.get("LLM_BASE_URL") or "").rstrip("/")
        self.api_key = os.environ.get("LLM_API_KEY") or ""
        self.model = os.environ.get("LLM_MODEL") or ""

    def is_available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def describe(self) -> dict:
        # Never expose the key.
        return {"provider": self.name, "model": self.model or "unconfigured"}

    def complete_json(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        if not self.is_available():
            raise ProviderUnavailable(
                "LLM provider is not configured. Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL."
            )
        import json as _json

        # NOTE: the API key is used only in the Authorization header. It is never
        # logged, persisted, or returned to callers.
        try:
            with self._httpx.Client(timeout=float(os.environ.get("LLM_TIMEOUT_S") or "30")) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json={
                        "model": self.model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": messages,
                    },
                )
        except Exception:
            raise ProviderFailure("LLM request failed.")
        if resp.status_code != 200:
            raise ProviderFailure(f"LLM provider returned HTTP {resp.status_code}.")
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            parsed = _json.loads(text)
        except Exception:
            raise ProviderFailure("LLM returned malformed JSON.")
        if not isinstance(parsed, dict):
            raise ProviderFailure("LLM returned malformed JSON.")
        return parsed


def get_provider() -> LLMProvider:
    """Select provider from environment. Defaults to deterministic (offline-safe)."""
    which = (os.environ.get("LLM_PROVIDER") or "deterministic").strip().lower()
    if which in ("openai-compatible", "openai", "compatible"):
        return OpenAICompatibleProvider()
    return DeterministicProvider()


def provider_status() -> dict:
    provider = get_provider()
    available = provider.is_available()
    desc = provider.describe()
    return {
        "available": available,
        "provider": desc.get("provider"),
        "model": desc.get("model"),
        "message": (
            "Agent ready."
            if available
            else "Agent unavailable — deterministic reconciliation is still available."
        ),
    }
