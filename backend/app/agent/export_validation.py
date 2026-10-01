"""Export validation (Phase 6). Before any PDF is generated:

1. load requested version
2. validate the version content
3. verify stored reconciliation snapshot
4. verify referenced findings (against the snapshot run, not latest)
5. verify evidence references
6. verify rule version
7. verify monetary values
8. verify notice metadata
9. verify review state (reported, and stale-approval safe)

Never silently generate a potentially stale document.
"""

from app import database
from app.agent import validation as validation_mod
from app.agent import versions as versions_mod
from app.parsers import gst_rules


def _loads(raw, default):
    import json as _json

    try:
        return _json.loads(raw or "")
    except (ValueError, TypeError):
        return default


def validate_version_for_export(draft_id: str, version: int | None = None) -> tuple[bool, list[str], dict | None]:
    """Return (ok, errors, version_dict). Errors are human-readable."""
    errors: list[str] = []
    head = database.get_reply_draft(draft_id)
    if head is None:
        return False, ["Draft not found."], None
    versions = versions_mod.list_versions(draft_id)
    if version is None:
        version = head["current_version"] or 1
    selected = next((v for v in versions if v["version"] == version), None)
    if selected is None:
        return False, [f"Version {version} not found."], None

    # 3. Stored reconciliation snapshot must exist and have run.
    snap = selected.get("reconSnapshot") or {}
    if not snap.get("ran") or not snap.get("runId"):
        return False, ["Version has no reconciliation snapshot; re-run reconciliation."], selected

    # Snapshot run must still exist (findings fetched from it, never recalculated).
    try:
        from app.services import reconciliation as recon_service

        snapshot_recon = recon_service.get_reconciliation_run(snap["runId"])
    except KeyError:
        return False, ["Snapshot reconciliation run is missing; cannot export."], selected

    # 4. Referenced findings must belong to the snapshot run.
    snapshot_finding_ids = {f["id"] for f in snapshot_recon.get("findings") or []}
    stale = sorted(set(selected.get("findingIds") or []) - snapshot_finding_ids)
    if stale:
        errors.append(f"Version references findings outside its snapshot: {', '.join(stale)}.")

    # 5. Evidence references must still exist.
    live_evidence = {r["id"] for r in database.list_return_documents(head["notice_id"])}
    gone = sorted(set(selected.get("evidenceIds") or []) - live_evidence)
    if gone:
        errors.append(f"Version references missing evidence: {', '.join(gone)}.")

    # 6. Rule version must be the current known version.
    if (selected.get("ruleVersion") or "") != gst_rules.RULE_VERSION:
        errors.append(
            f"Rule version {selected.get('ruleVersion') or 'unknown'} is not current "
            f"({gst_rules.RULE_VERSION})."
        )

    # 2+7+8. Full content validation against snapshot truth.
    notice = database.get_notice(head["notice_id"])
    if notice is None:
        return False, ["Notice not found."], selected
    snap_numbers = {
        snap.get("noticeDifference"), snap.get("calculatedDifference"),
        snap.get("explainedAmount"), snap.get("unexplainedAmount"),
        notice["difference_amount"], gst_rules.TOLERANCE_INR,
    }
    allowed = {round(float(v), 2) for v in snap_numbers if v is not None}
    for fid in selected.get("findingIds") or []:
        for f in snapshot_recon.get("findings") or []:
            if f["id"] == fid and f.get("amount") is not None:
                allowed.add(round(float(f["amount"]), 2))
    rows = database.list_return_rows(head["notice_id"])
    known_invoices = {(r["invoice_number"] or "").strip().upper() for r in rows}
    known_invoices.discard("")
    ok, content_errors = validation_mod.validate_content(
        selected.get("content") or "",
        notice_number=(notice["notice_number"], notice["id"]),
        tax_period=notice["tax_period"],
        gstin=notice["gstin"],
        allowed_numbers=allowed,
        valid_findings=snapshot_finding_ids,
        valid_evidence=live_evidence,
        expected_rule=validation_mod._expected_rule(notice["notice_type"]),
        rule_version=gst_rules.RULE_VERSION,
        known_invoices=known_invoices,
    )
    if not ok:
        errors.extend(content_errors)

    # 9. Review state is reported (and approvals are snapshot-pinned, never stale).
    review = database.get_review_by_draft(draft_id)
    review_state = {
        "status": selected.get("reviewStatus"),
        "approvedVersion": selected["version"] if selected.get("reviewStatus") == "APPROVED" else None,
        "reviewedVersion": (review["version"] if review else None),
    }
    selected = {**selected, "exportReviewState": review_state}
    return (len(errors) == 0), errors, selected
