"""Agent orchestrator (Phase 4). Bounded tool-calling loop with an explicit,
persisted state machine. The LLM proposes and narrates; deterministic tools
and guardrails decide what is true.

Loop (max 8 tool iterations):
  get_notice_context -> get_reconciliation -> get_evidence ->
  [get_finding_lineage x N] -> get_missing_evidence ->
  decision (LLM proposal, guardrail-validated) -> generate_reply_draft
"""

import uuid

from app import database
from app.agent import guardrails, prompts, schemas, tools
from app.agent.provider import LLMProvider, ProviderFailure, ProviderUnavailable, get_provider


def _record_step(run_id: str, sequence: int, tool_name: str, tool_input: dict,
                 summary: str, status: str) -> None:
    database.create_agent_step(run_id, sequence, tool_name, tool_input, summary, status)


def _call_tool(run_id: str, sequence: int, tool_name: str, **kwargs) -> tuple[dict, int]:
    """Run one tool, persist its trace step, never leak internals on failure."""
    fn = tools.TOOLS[tool_name]
    safe_input = {k: v for k, v in kwargs.items() if k != "run_id"}
    try:
        if tool_name == "generate_reply_draft":
            out = fn(kwargs["notice_id"], kwargs["decision"], run_id,
                     kwargs.get("explanation"))
        elif tool_name == "get_finding_lineage":
            out = fn(kwargs["finding_id"])
        else:
            out = fn(kwargs["notice_id"])
        _record_step(run_id, sequence, tool_name, safe_input, out.get("summary", ""), "ok")
        return out, sequence + 1
    except (KeyError, LookupError) as e:
        summary = f"Tool returned no data ({type(e).__name__}). No result invented."
        _record_step(run_id, sequence, tool_name, safe_input, summary, "failed")
        return {"data": None, "summary": summary}, sequence + 1
    except Exception:
        summary = "Tool failed. No result invented."
        _record_step(run_id, sequence, tool_name, safe_input, summary, "failed")
        return {"data": None, "summary": summary}, sequence + 1


def _set_status(run_id: str, status: str, **fields) -> None:
    database.update_agent_run(run_id, status=status, **fields)


def _propose_decision(provider: LLMProvider, context: dict, recon: dict,
                      evidence: dict, allowed: list[str]) -> dict | None:
    """Ask the LLM for a decision proposal. Returns None on abstain/failure."""
    try:
        raw = provider.complete_json(
            prompts.decision_proposal_prompt(context, recon, evidence, allowed),
            purpose="decision_proposal",
        )
    except (ProviderUnavailable, ProviderFailure):
        return None
    if not isinstance(raw, dict):
        return None
    decision = str(raw.get("decision") or "").upper()
    if decision == "ABSTAIN" or decision not in schemas.ALLOWED_DECISIONS:
        return None
    return {"decision": decision, "reasoningSummary": str(raw.get("reasoningSummary") or "")}


def _narrate(provider: LLMProvider, decision: str, recon_summary: dict,
             missing: list[dict], fallback: str) -> str:
    try:
        raw = provider.complete_json(
            prompts.narration_prompt(decision, recon_summary, missing), purpose="narration"
        )
        text = str((raw or {}).get("reasoningSummary") or "").strip()
    except (ProviderUnavailable, ProviderFailure):
        return fallback
    if not text or prompts.contains_banned_phrasing(text):
        return fallback
    return text


def run_agent(notice_id: str, provider: LLMProvider | None = None) -> dict:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    provider = provider or get_provider()
    desc = provider.describe()

    run_id = f"arun_{uuid.uuid4().hex[:12]}"
    database.create_agent_run(run_id, notice_id, "ANALYZING", desc.get("provider"), desc.get("model"))
    seq = 1

    try:
        # 1-3. Core context tools (fixed valid sequence).
        ctx_out, seq = _call_tool(run_id, seq, "get_notice_context", notice_id=notice_id)
        if ctx_out["data"] is None:
            raise RuntimeError("Notice context unavailable.")
        _set_status(run_id, "ANALYZING")
        recon_out, seq = _call_tool(run_id, seq, "get_reconciliation", notice_id=notice_id)
        _set_status(run_id, "INSPECTING_EVIDENCE")
        if recon_out.get("data", {}).get("ran"):
            database.create_audit_event(
                notice_id, "AGENT", run_id, "RECONCILIATION_REVIEWED", "agent_run", run_id,
                {"reconStatus": recon_out["data"].get("status")},
            )
        ev_out, seq = _call_tool(run_id, seq, "get_evidence", notice_id=notice_id)

        recon = (recon_out.get("data") or {})
        recon_status = recon.get("status") if recon.get("ran") else None

        # 4. Inspect up to 2 key findings' lineage (bounded).
        if recon.get("ran"):
            key_findings = [f for f in recon.get("findings") or []
                            if f["category"] in ("MATCHED_COMPONENT", "MISMATCH")][:2]
            for f in key_findings:
                if seq > schemas.MAX_TOOL_ITERATIONS - 3:
                    break
                _call_tool(run_id, seq, "get_finding_lineage", notice_id=notice_id,
                           finding_id=f["id"])
                seq += 1

        # 5. Missing evidence.
        _set_status(run_id, "EVALUATING")
        missing_out, seq = _call_tool(run_id, seq, "get_missing_evidence", notice_id=notice_id)
        missing = missing_out.get("data") or []
        if missing:
            database.create_audit_event(
                notice_id, "AGENT", run_id, "EVIDENCE_REQUESTED", "agent_run", run_id,
                {"missingCount": len(missing)},
            )

        # 6. Decision: deterministic allowed set + default; LLM may propose within it.
        _set_status(run_id, "EVALUATING")
        allowed = list(guardrails.allowed_decisions(recon_status))
        fallback_decision = guardrails.default_decision(recon_status, len(missing))
        proposal = _propose_decision(
            provider,
            ctx_out["data"],
            {**recon, "findings": recon.get("findings") or []} if recon.get("ran") else {},
            ev_out.get("data") or {},
            allowed,
        )
        selected = fallback_decision
        if proposal and proposal["decision"] in allowed:
            selected = proposal["decision"]

        candidate = schemas.AgentDecision(
            decision=selected,
            reasoningSummary=proposal["reasoningSummary"] if proposal else "",
            findingIds=[f["id"] for f in (recon.get("findings") or [])] if recon.get("ran") else [],
            evidenceIds=[e["evidenceId"] for e in (ev_out.get("data") or {}).get("verified", [])]
            + [e["evidenceId"] for e in (ev_out.get("data") or {}).get("partial", [])],
            missingEvidence=missing,
            requiresHumanReview=True,
        )
        ok, violations = guardrails.validate_decision(candidate, notice_id)
        if not ok:
            # Never trust the proposal: fall back to the constrained default.
            candidate = schemas.AgentDecision(
                decision=fallback_decision,
                reasoningSummary="",
                findingIds=candidate.findingIds,
                evidenceIds=candidate.evidenceIds,
                missingEvidence=missing,
                requiresHumanReview=True,
            )
            ok, violations = guardrails.validate_decision(candidate, notice_id)
            if not ok:
                raise RuntimeError(f"Guardrail fallback rejected: {'; '.join(violations)}")
        _record_step(
            run_id, seq, "decision",
            {"allowed": allowed},
            f"Decision {candidate.decision} validated against reconciliation {recon_status or 'NOT_RUN'}.",
            "ok",
        )
        seq += 1

        # 7. Narration (LLM wording only; deterministic fallback always available).
        _set_status(run_id, "READY_FOR_DRAFT")
        fallback_summary = (
            f"Based on the uploaded records, reconciliation {recon_status or 'has not run'}: "
            f"Rs. {recon.get('explainedAmount', 0)} explained, "
            f"Rs. {recon.get('unexplainedAmount', 0)} unexplained. "
            f"{len(missing)} missing evidence items. Review required before submission."
        )
        candidate.reasoningSummary = _narrate(
            provider, candidate.decision,
            {"status": recon_status, "explained": recon.get("explainedAmount"),
             "unexplained": recon.get("unexplainedAmount")},
            missing, fallback_summary,
        ) or (proposal["reasoningSummary"] if proposal else fallback_summary)

        # 8. Reply draft (template-backed; the optional LLM explanatory
        # paragraph is fetched first and verified inside the draft builder, so
        # v1 snapshots the exact head content — no post-hoc mutation).
        explanation = _fetch_explanation(provider, candidate.decision, notice_id, recon)
        draft_out, seq = _call_tool(
            run_id, seq, "generate_reply_draft",
            notice_id=notice_id, decision=candidate.decision, explanation=explanation,
        )
        draft_id = (draft_out.get("data") or {}).get("draftId")

        # Milestone status; requiresHumanReview=true means a human must review
        # before anything else happens (review-only system).
        final_status = "WAITING_FOR_EVIDENCE" if missing else "DRAFT_READY"
        _set_status(
            run_id, final_status,
            decision=candidate.decision,
            reasoning_summary=candidate.reasoningSummary,
            requires_review=True,
            draft_id=draft_id,
            tool_iterations=seq - 1,
        )
        return get_agent_run(run_id)
    except (ProviderUnavailable, ProviderFailure) as e:
        _set_status(run_id, "ERROR", error=str(e), tool_iterations=seq - 1)
        return get_agent_run(run_id)
    except Exception as e:
        _set_status(run_id, "ERROR", error=f"Agent run failed: {type(e).__name__}.", tool_iterations=seq - 1)
        return get_agent_run(run_id)


def _fetch_explanation(provider: LLMProvider, decision: str,
                       notice_id: str, recon: dict) -> str | None:
    """Fetch one explanatory paragraph; returns None on any failure so the
    template-only draft is used. Verification happens in the draft builder."""
    notice = database.get_notice(notice_id)
    facts = {
        "noticeDifference": (recon or {}).get("noticeDifference"),
        "explained": (recon or {}).get("explainedAmount"),
        "unexplained": (recon or {}).get("unexplainedAmount"),
        "decision": decision,
    }
    try:
        raw = provider.complete_json(
            prompts.draft_prose_prompt(decision, facts), purpose="draft_prose"
        )
        explanation = str((raw or {}).get("explanation") or "").strip()
    except (ProviderUnavailable, ProviderFailure):
        return None
    return explanation or None


def get_agent_run(run_id: str) -> dict:
    row = database.get_agent_run(run_id)
    if row is None:
        raise KeyError(run_id)
    steps = [
        {
            "sequence": s["sequence"],
            "tool": s["tool_name"],
            "purpose": tools.TOOL_PURPOSES.get(s["tool_name"], s["tool_name"]),
            "resultSummary": s["output_summary"],
            "status": s["status"],
            "createdAt": s["created_at"],
        }
        for s in database.list_agent_steps(run_id)
    ]
    return {
        "id": row["id"],
        "noticeId": row["notice_id"],
        "status": row["status"],
        "decision": row["decision"],
        "reasoningSummary": row["reasoning_summary"],
        "requiresHumanReview": bool(row["requires_review"]),
        "provider": row["provider"],
        "model": row["model"],
        "toolIterations": row["tool_iterations"],
        "error": row["error"],
        "draftId": row["draft_id"],
        "createdAt": row["created_at"],
        "completedAt": row["completed_at"],
        "steps": steps,
    }


def list_agent_runs(notice_id: str) -> list[dict]:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    runs = []
    for row in database.list_agent_runs(notice_id):
        runs.append({
            "id": row["id"],
            "noticeId": row["notice_id"],
            "status": row["status"],
            "decision": row["decision"],
            "requiresHumanReview": bool(row["requires_review"]),
            "toolIterations": row["tool_iterations"],
            "draftId": row["draft_id"],
            "createdAt": row["created_at"],
            "completedAt": row["completed_at"],
        })
    return runs
