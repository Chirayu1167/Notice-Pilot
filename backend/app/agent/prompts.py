"""Agent prompts (Phase 4). Structured-data-only prompts: the LLM receives
notice metadata, reconciliation results, findings, and evidence summaries —
never raw files, credentials, paths, or stack traces."""

import json

from app.agent import schemas

SYSTEM_PROMPT = """You are the narration assistant for NoticePilot GST, a review-and-preparation \
system. You are an orchestrator and narrator, NOT a source of financial truth.

Hard rules:
- NEVER calculate, invent, or alter GST amounts, dates, GSTINs, invoice numbers, \
evidence references, legal sections, or rules. Use only values provided in tool outputs.
- NEVER claim evidence exists when the tools say it does not.
- NEVER claim a difference is explained when an unexplained residual remains.
- NEVER provide definitive legal advice or guarantees. Use hedging review language: \
"Based on the uploaded records...", "Reconciliation indicates...", "Additional evidence \
is required...", "Review required before submission."
- NEVER use these phrases: "you will win", "proves the department is wrong", \
"legally valid", "guaranteed acceptance", "filed", "submitted", "accepted", "approved".
- Respond with a single JSON object only, matching the requested shape.
- Keep summaries factual and concise. No chain-of-thought, no internal reasoning."""


def decision_proposal_prompt(context: dict, recon: dict, evidence: dict, allowed: list[str]) -> list[dict]:
    user = {
        "task": "propose_decision",
        "allowedDecisions": allowed,
        "notice": context,
        "reconciliation": {
            "status": recon.get("status"),
            "noticeDifference": recon.get("noticeDifference"),
            "calculatedDifference": recon.get("calculatedDifference"),
            "explainedAmount": recon.get("explainedAmount"),
            "unexplainedAmount": recon.get("unexplainedAmount"),
            "ruleVersion": recon.get("ruleVersion"),
            "findings": [
                {"id": f["id"], "category": f["category"], "amount": f["amount"], "status": f["status"]}
                for f in recon.get("findings") or []
            ],
        },
        "evidence": {
            "verifiedCount": len(evidence.get("verified") or []),
            "partialCount": len(evidence.get("partial") or []),
            "missing": evidence.get("missing") or [],
        },
        "responseShape": {
            "decision": "one of allowedDecisions, or ABSTAIN",
            "reasoningSummary": "2-3 factual sentences using only the values above",
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user, default=str)},
    ]


def narration_prompt(decision: str, recon_summary: dict, missing: list[dict]) -> list[dict]:
    user = {
        "task": "narrate_decision",
        "decision": decision,
        "reconciliation": recon_summary,
        "missingEvidence": missing,
        "responseShape": {"reasoningSummary": "2-3 factual sentences, review-required language"},
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user, default=str)},
    ]


def draft_prose_prompt(decision: str, facts: dict) -> list[dict]:
    user = {
        "task": "draft_explanation_paragraph",
        "decision": decision,
        "facts": facts,
        "responseShape": {
            "explanation": (
                "One short paragraph rephrasing ONLY the supplied facts for a GST officer. "
                "No new amounts, dates, identifiers, sections, or conclusions."
            )
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user, default=str)},
    ]


BANNED_PHRASES = (
    "you will win",
    "proves the department is wrong",
    "legally valid",
    "guaranteed acceptance",
    "guarantee",
    "filed",
    "submitted",
    "accepted",
    "approved",
)


def contains_banned_phrasing(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [phrase for phrase in BANNED_PHRASES if phrase in lowered]
