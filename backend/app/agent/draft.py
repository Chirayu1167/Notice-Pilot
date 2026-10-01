"""Reply draft generation (Phase 4). Deterministic/template-backed.

All financial values are populated from backend data. The LLM may supply one
explanatory paragraph, which is then verified: every currency figure in the
final text must match a backend fact, and banned phrasing is rejected.
"""

import re
import uuid

from app import database
from app.agent import prompts
from app.parsers import gst_rules

CURRENCY_RE = re.compile(r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)")


def _parse_amount(raw: str) -> float | None:
    try:
        return round(float(raw.replace(",", "")), 2)
    except ValueError:
        return None


def allowed_numbers(notice: dict, recon: dict | None) -> set[float]:
    numbers: set[float] = set()
    for value in (
        (notice or {}).get("difference_amount"),
        ((recon or {}).get("noticeDifference")),
        ((recon or {}).get("calculatedDifference")),
        ((recon or {}).get("explainedAmount")),
        ((recon or {}).get("unexplainedAmount")),
    ):
        if value is not None:
            numbers.add(round(float(value), 2))
    if recon:
        for f in recon.get("findings") or []:
            if f.get("amount") is not None:
                numbers.add(round(float(f["amount"]), 2))
    numbers.add(round(float(gst_rules.TOLERANCE_INR), 2))
    return numbers


def verify_draft_numbers(content: str, allowed: set[float]) -> tuple[bool, list[float]]:
    """Every currency figure in the draft must come from backend facts."""
    bad: list[float] = []
    for raw in CURRENCY_RE.findall(content or ""):
        value = _parse_amount(raw)
        if value is None:
            continue
        if not any(abs(value - a) <= 0.005 for a in allowed):
            bad.append(value)
    return (len(bad) == 0), bad


def _inr(value) -> str:
    if value is None:
        return "not stated"
    return f"Rs. {float(value):,.2f}"


def _rule_citation(notice_type: str, rule_version: str | None) -> str:
    rule = "88C" if (notice_type or "").upper() == "DRC-01B" else (
        "88D" if (notice_type or "").upper() == "DRC-01C" else "the applicable rule"
    )
    return f"[Rule {rule} / {rule_version or gst_rules.RULE_VERSION}]"


def build_reply_draft(notice_id: str, decision: str, run_id: str,
                      explanation: str | None = None) -> dict:
    notice = database.get_notice(notice_id)
    if notice is None:
        raise KeyError(notice_id)
    from app.services import reconciliation as recon_service

    try:
        recon = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        recon = None

    findings = recon.get("findings") if recon else []
    returns = list(database.list_return_documents(notice_id))
    rule_version = (recon or {}).get("ruleVersion") or gst_rules.RULE_VERSION
    rule_cite = _rule_citation(notice["notice_type"], rule_version)

    if decision == "CONTEST":
        position = (
            "Based on the uploaded records, the taxpayer contests the demand: "
            "reconciliation indicates the reported figures reconcile within tolerance."
        )
    elif decision == "PARTIAL_ACCEPT":
        position = (
            "Based on the uploaded records, the taxpayer partially accepts the difference "
            "to the extent of the unexplained residual and requests verification of the remainder."
        )
    else:
        position = (
            "Based on the uploaded records, additional evidence is required before a "
            "substantive response can be prepared."
        )

    lines: list[str] = []
    lines.append("DRAFT RESPONSE — REVIEW REQUIRED BEFORE SUBMISSION.")
    lines.append("NoticePilot does not submit responses to the GST portal.")
    lines.append("")
    lines.append(f"Notice reference: {notice['notice_number'] or notice['id']}")
    lines.append(f"Notice type: {notice['notice_type'] or 'UNKNOWN'}")
    lines.append(f"Tax period: {notice['tax_period'] or 'not stated'}")
    lines.append(f"GSTIN: {notice['gstin'] or 'not stated'}")
    lines.append("")
    if recon:
        lines.append(
            f"Identified difference: {_inr(recon['noticeDifference'])} "
            f"(notice) vs calculated {_inr(recon['calculatedDifference'])} {rule_cite}."
        )
        lines.append(
            f"Reconciliation indicates {_inr(recon['explainedAmount'])} explained and "
            f"{_inr(recon['unexplainedAmount'])} unexplained."
        )
    else:
        lines.append("No reconciliation has been run for this notice.")
    lines.append("")
    lines.append(f"Position ({decision}): {position}")
    lines.append("")
    lines.append("Factual findings:")
    if findings:
        for f in findings:
            cite = f"[Finding {f['id']}]"
            rows = ", ".join((f.get("sourceRows") or [])[:5])
            extra = f" Source rows: {rows}." if rows else ""
            amount = _inr(f.get("amount")) if f.get("amount") is not None else "no amount"
            lines.append(f"- {f['category']}: {amount} ({f['status']}) {cite}.{extra}")
    else:
        lines.append("- No findings recorded.")
    lines.append("")
    lines.append("Evidence references:")
    if returns:
        for r in returns:
            lines.append(
                f"- [Evidence {r['id']}] {r['source']} for period {r['period'] or 'unknown'}: "
                f"{r['filename']} ({r['row_count']} rows)."
            )
    else:
        lines.append("- No return documents uploaded.")
    lines.append("")
    lines.append(f"Rule reference: {rule_cite}.")
    lines.append("Review required before submission.")

    content = "\n".join(lines)
    evidence_ids = sorted({r["id"] for r in returns})
    finding_ids = sorted({f["id"] for f in findings})

    # Optional LLM explanatory paragraph, attached BEFORE v1 is snapshotted so
    # the head content and v1 are always identical. Verified like everything else.
    if explanation:
        allowed = allowed_numbers({"difference_amount": notice["difference_amount"]}, recon)
        content, _ = attach_llm_prose(content, explanation, allowed)

    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    database.create_reply_draft(
        draft_id, notice_id, run_id or None, decision, content,
        evidence_ids, finding_ids, rule_version, "draft", True,
    )
    from app.agent import versions as versions_mod

    versions_mod.ensure_v1(database.get_reply_draft(draft_id))
    database.create_audit_event(
        notice_id, "AGENT", run_id or "", "DRAFT_GENERATED", "draft", draft_id,
        {"decision": decision, "version": 1},
    )
    return {
        "id": draft_id,
        "noticeId": notice_id,
        "agentRunId": run_id,
        "decision": decision,
        "content": content,
        "evidenceIds": evidence_ids,
        "findingIds": finding_ids,
        "ruleVersion": rule_version,
        "status": "draft",
        "requiresReview": True,
    }


def attach_llm_prose(content: str, explanation: str, allowed: set[float]) -> tuple[str, bool]:
    """Insert one LLM paragraph after the position line, if it verifies cleanly."""
    explanation = (explanation or "").strip()
    if not explanation:
        return content, False
    if prompts.contains_banned_phrasing(explanation):
        return content, False
    ok, _ = verify_draft_numbers(explanation, allowed)
    if not ok:
        return content, False
    marker = "Factual findings:"
    if marker in content:
        return content.replace(marker, f"Explanation: {explanation}\n\n{marker}", 1), True
    return content + f"\n\nExplanation: {explanation}", True
