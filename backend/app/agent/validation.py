"""Draft fact validation (Phase 5). Machine-checkable factual integrity.

Verifies, against backend records only:
1. Every monetary figure exists in backend facts.
2. Every finding citation exists in the latest reconciliation run.
3. Every evidence citation exists as a return document of the notice.
4. Every rule citation is known and versioned.
5. Notice number matches.
6. Tax period matches.
7. GSTIN, when present, matches.
8. Invoice numbers, when present, match uploaded rows.
9. No automatic filing / guarantee claims exist.
10. Review-required language remains present.

This is factual-integrity checking, not a legal-language verifier.
"""

import re

from app import database
from app.agent import draft as draft_mod
from app.agent import prompts
from app.parsers import gst_rules

FINDING_RE = re.compile(r"\[Finding\s+([^\]]+)\]")
EVIDENCE_RE = re.compile(r"\[Evidence\s+([^\]]+)\]")
RULE_RE = re.compile(r"\[Rule\s+([^\]]+)\]")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
INVOICE_RE = re.compile(r"\bINV-[A-Z0-9][A-Z0-9\-]*\b")

REVIEW_REQUIRED_PHRASE = "review required before submission"


def _line_value(content: str, label: str) -> str | None:
    for line in (content or "").splitlines():
        if line.strip().lower().startswith(label.lower()):
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def validate_draft(content: str, notice_id: str) -> tuple[bool, list[str]]:
    """Return (ok, errors). All checks are deterministic backend comparisons."""
    notice = database.get_notice(notice_id)
    if notice is None:
        return False, ["Notice not found."]
    try:
        from app.services import reconciliation as recon_service

        recon = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        recon = None

    # 1. Monetary figures.
    allowed = draft_mod.allowed_numbers(
        {"difference_amount": notice["difference_amount"]}, recon
    )
    if recon:
        valid_findings: set[str] | None = {f["id"] for f in recon.get("findings") or []}
    else:
        valid_findings = None
    rows = database.list_return_rows(notice_id)
    known_invoices = {(r["invoice_number"] or "").strip().upper() for r in rows}
    known_invoices.discard("")
    return validate_content(
        content,
        notice_number=(notice["notice_number"], notice["id"]),
        tax_period=notice["tax_period"],
        gstin=notice["gstin"],
        allowed_numbers=allowed,
        valid_findings=valid_findings,
        valid_evidence={r["id"] for r in database.list_return_documents(notice_id)},
        expected_rule=_expected_rule(notice["notice_type"]),
        rule_version=gst_rules.RULE_VERSION,
        known_invoices=known_invoices,
    )


def _expected_rule(notice_type: str | None) -> str | None:
    upper = (notice_type or "UNKNOWN").upper()
    if upper == "DRC-01B":
        return "88C"
    if upper == "DRC-01C":
        return "88D"
    return None


def validate_content(
    content: str,
    *,
    notice_number: tuple[str | None, str],
    tax_period: str | None,
    gstin: str | None,
    allowed_numbers: set[float],
    valid_findings: set[str] | None,
    valid_evidence: set[str],
    expected_rule: str | None,
    rule_version: str,
    known_invoices: set[str],
) -> tuple[bool, list[str]]:
    """Shared factual-integrity core. Callers supply backend truth explicitly,
    so historical versions can be checked against their own snapshot."""
    errors: list[str] = []
    text = content or ""

    # 1. Monetary figures.
    ok, bad = draft_mod.verify_draft_numbers(text, allowed_numbers)
    if not ok:
        errors.append(f"Figures not present in backend records: {sorted(set(bad))}.")

    # 2. Finding citations.
    cited_findings = [m.group(1).strip() for m in FINDING_RE.finditer(text)]
    if valid_findings is not None:
        for fid in cited_findings:
            if fid not in valid_findings:
                errors.append(f"Unknown or stale finding citation '{fid}'.")
    elif cited_findings:
        errors.append("Finding citations present but no reconciliation run exists.")

    # 3. Evidence citations.
    cited_evidence = [m.group(1).strip() for m in EVIDENCE_RE.finditer(text)]
    for eid in cited_evidence:
        if eid not in valid_evidence:
            errors.append(f"Unknown evidence citation '{eid}'.")

    # 4. Rule citations.
    for raw in (m.group(1).strip() for m in RULE_RE.finditer(text)):
        parts = [p.strip() for p in raw.split("/")]
        rule_no = parts[0]
        if expected_rule and rule_no != expected_rule:
            errors.append(f"Rule citation '{raw}' does not match notice type.")
        elif expected_rule is None and rule_no not in ("88C", "88D"):
            errors.append(f"Unknown rule citation '{raw}'.")
        if len(parts) > 1 and parts[1] != rule_version:
            errors.append(f"Rule version '{parts[1]}' is not the current {rule_version}.")

    # 5. Notice number.
    ref = _line_value(text, "Notice reference")
    if ref is None:
        errors.append("Notice reference line is missing.")
    elif ref not in notice_number:
        errors.append("Notice reference does not match backend records.")

    # 6. Tax period.
    period = _line_value(text, "Tax period")
    if period is None:
        errors.append("Tax period line is missing.")
    elif (tax_period or "not stated") != period and period != "not stated":
        errors.append("Tax period does not match backend records.")

    # 7. GSTIN tokens.
    for token in set(GSTIN_RE.findall(text)):
        if gstin and token != gstin:
            errors.append(f"GSTIN '{token}' does not match backend records.")

    # 8. Invoice numbers.
    for token in set(INVOICE_RE.findall(text.upper())):
        if token not in known_invoices:
            errors.append(f"Invoice '{token}' does not match uploaded return rows.")

    # 9. Filing/guarantee claims.
    banned = prompts.contains_banned_phrasing(text)
    if banned:
        errors.append(f"Conclusive/filing language present: {sorted(set(banned))}.")

    # 10. Review-required language.
    if REVIEW_REQUIRED_PHRASE not in text.lower():
        errors.append("Review-required statement is missing.")

    return (len(errors) == 0), errors
