"""Draft versioning (Phase 5). Versions are immutable; edits create new versions.

Each version snapshots the reconciliation summary so the PDF and history stay
truthful even if reconciliation reruns later. The PDF generator only formats
these snapshots — it never calculates.
"""

import json
import uuid

from app import database


def recon_snapshot(notice_id: str) -> dict:
    try:
        from app.services import reconciliation as recon_service

        recon = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        return {"ran": False}
    return {
        "ran": True,
        "runId": recon["id"],
        "status": recon["status"],
        "noticeDifference": recon["noticeDifference"],
        "calculatedDifference": recon["calculatedDifference"],
        "explainedAmount": recon["explainedAmount"],
        "unexplainedAmount": recon["unexplainedAmount"],
        "ruleVersion": recon.get("ruleVersion"),
        "findingCount": len(recon.get("findings") or []),
    }


def _loads(raw, default):
    try:
        return json.loads(raw or "")
    except (ValueError, TypeError):
        return default


def version_to_dict(v) -> dict:
    return {
        "id": v["id"],
        "draftId": v["draft_id"],
        "version": v["version"],
        "content": v["content"],
        "decision": v["decision"],
        "findingIds": _loads(v["finding_ids_json"], []),
        "evidenceIds": _loads(v["evidence_ids_json"], []),
        "ruleVersion": v["rule_version"],
        "reconSnapshot": _loads(v["recon_snapshot_json"], {}),
        "createdBy": v["created_by"],
        "agentRunId": v["agent_run_id"],
        "parentVersionId": v["parent_version_id"],
        "reviewStatus": v["review_status"],
        "createdAt": v["created_at"],
    }


def ensure_v1(draft_row) -> None:
    """Backfill an immutable v1 for drafts created before versioning existed."""
    if database.list_draft_versions(draft_row["id"]):
        return
    version_id = f"dver_{uuid.uuid4().hex[:12]}"
    database.create_draft_version(
        version_id, draft_row["id"], 1, draft_row["content"], draft_row["decision"],
        _loads(draft_row["finding_ids_json"], []), _loads(draft_row["evidence_ids_json"], []),
        draft_row["rule_version"], recon_snapshot(draft_row["notice_id"]),
        "AGENT", draft_row["agent_run_id"], None,
    )
    if (draft_row["review_status"] or "PENDING_REVIEW") != "PENDING_REVIEW":
        database.set_version_review_status(version_id, draft_row["review_status"])


def create_version(draft_id: str, content: str, created_by: str,
                   agent_run_id: str | None = None) -> dict:
    """Create the next immutable version. Refreshes refs/snapshot from backend."""
    head = database.get_reply_draft(draft_id)
    if head is None:
        raise KeyError(draft_id)
    ensure_v1(head)
    existing = database.list_draft_versions(draft_id)
    from app.parsers import gst_rules
    from app.services import reconciliation as recon_service

    try:
        recon = recon_service.get_latest_reconciliation(head["notice_id"])
    except LookupError:
        recon = None
    finding_ids = sorted({f["id"] for f in (recon.get("findings") or [])}) if recon else []
    returns = database.list_return_documents(head["notice_id"])
    evidence_ids = sorted({r["id"] for r in returns})
    rule_version = (recon.get("ruleVersion") if recon else None) or gst_rules.RULE_VERSION
    parent = max(existing, key=lambda v: v["version"]) if existing else None
    new_version = (parent["version"] if parent else 0) + 1
    version_id = f"dver_{uuid.uuid4().hex[:12]}"
    database.create_draft_version(
        version_id, draft_id, new_version, content, head["decision"],
        finding_ids, evidence_ids, rule_version,
        recon_snapshot(head["notice_id"]), created_by, agent_run_id,
        parent["id"] if parent else None,
    )
    return version_to_dict(database.get_draft_version(draft_id, new_version))


def list_versions(draft_id: str) -> list[dict]:
    head = database.get_reply_draft(draft_id)
    if head is None:
        raise KeyError(draft_id)
    ensure_v1(head)
    return [version_to_dict(v) for v in database.list_draft_versions(draft_id)]
