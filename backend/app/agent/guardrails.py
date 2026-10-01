"""Decision guardrails (Phase 4). Deterministic validation of agent decisions.

The backend never trusts raw LLM output. Every decision is checked against
reconciliation facts and evidence state before it is accepted.
"""

from app import database
from app.agent import schemas
from app.parsers import gst_rules


def allowed_decisions(recon_status: str | None) -> tuple[str, ...]:
    if not recon_status:
        return ("INSUFFICIENT_EVIDENCE",)
    return schemas.ALLOWED_BY_RECON_STATUS.get((recon_status or "").upper(), ("INSUFFICIENT_EVIDENCE",))


def default_decision(recon_status: str | None, missing_count: int) -> str:
    """Guardrail-constrained fallback when the LLM abstains or errs."""
    allowed = allowed_decisions(recon_status)
    if (recon_status or "").upper() == "PARTIAL" and missing_count == 0:
        return "PARTIAL_ACCEPT" if "PARTIAL_ACCEPT" in allowed else allowed[0]
    if (recon_status or "").upper() == "MATCHED":
        return "CONTEST"
    return "INSUFFICIENT_EVIDENCE" if "INSUFFICIENT_EVIDENCE" in allowed else allowed[0]


def validate_decision(decision: schemas.AgentDecision, notice_id: str) -> tuple[bool, list[str]]:
    """Return (ok, violations). Pure deterministic checks against backend state."""
    violations: list[str] = []

    if decision.decision not in schemas.ALLOWED_DECISIONS:
        violations.append(f"Invalid decision '{decision.decision}'.")
        return False, violations

    notice = database.get_notice(notice_id)
    if notice is None:
        return False, ["Notice not found."]

    try:
        from app.services import reconciliation as recon_service

        recon = recon_service.get_latest_reconciliation(notice_id)
        recon_status = recon["status"]
    except LookupError:
        recon = None
        recon_status = None

    # 1. Decision must be allowed for the reconciliation status.
    allowed = allowed_decisions(recon_status)
    if decision.decision not in allowed:
        violations.append(
            f"Decision {decision.decision} is not allowed for reconciliation status "
            f"{recon_status or 'NOT_RUN'} (allowed: {', '.join(allowed)})."
        )

    # 2. CONTEST requires sufficient evidence: no missing return documents.
    if decision.decision == "CONTEST":
        returns = list(database.list_return_documents(notice_id))
        present = {r["source"] for r in returns}
        required = set(gst_rules.REQUIREMENTS.get((notice["notice_type"] or "UNKNOWN").upper(), []))
        lacking = sorted(required - present)
        if lacking:
            violations.append(
                f"CONTEST requires complete return data; missing: {', '.join(lacking)}."
            )
        if recon is None:
            violations.append("CONTEST requires a completed reconciliation run.")

    # 3. UNEXPLAINED residual must not be claimed as explained.
    if recon and (recon.get("unexplainedAmount") or 0) > gst_rules.TOLERANCE_INR:
        if decision.decision == "CONTEST":
            violations.append(
                f"Unexplained residual Rs. {recon['unexplainedAmount']:,.2f} remains; "
                f"the difference has not been fully explained."
            )

    # 4. Missing evidence forces human review.
    if decision.missingEvidence and not decision.requiresHumanReview:
        violations.append("Missing evidence requires requiresHumanReview=true.")

    # 5. Referenced finding IDs must exist in the latest run.
    if recon:
        valid_findings = {f["id"] for f in recon.get("findings") or []}
        for fid in decision.findingIds:
            if fid not in valid_findings:
                violations.append(f"Unknown finding ID '{fid}'.")
    elif decision.findingIds:
        violations.append("No reconciliation run exists, but finding IDs were referenced.")

    # 6. Referenced evidence IDs must exist as return documents of this notice.
    valid_evidence = {r["id"] for r in database.list_return_documents(notice_id)}
    for eid in decision.evidenceIds:
        if eid not in valid_evidence:
            violations.append(f"Unknown evidence ID '{eid}'.")

    # 7. requiresHumanReview must always be true in Phase 4 (review-only system).
    if not decision.requiresHumanReview:
        violations.append("requiresHumanReview must be true; the system is review-only.")

    return (len(violations) == 0), violations
