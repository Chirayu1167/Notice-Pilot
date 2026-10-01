"""Agent API (Phase 4). Review-only agentic workflow over deterministic tools."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database
from app.agent import orchestrator
from app.agent.provider import provider_status

router = APIRouter()


class DraftUpdate(BaseModel):
    content: str | None = None
    status: str | None = None


def _draft_to_dict(row) -> dict:
    import json as _json

    from app.agent import versions as versions_mod

    try:
        evidence_ids = _json.loads(row["evidence_ids_json"] or "[]")
    except (ValueError, TypeError):
        evidence_ids = []
    try:
        finding_ids = _json.loads(row["finding_ids_json"] or "[]")
    except (ValueError, TypeError):
        finding_ids = []
    review = database.get_review_by_draft(row["id"])
    if review is not None:
        import json as _json2

        try:
            review_validation = _json2.loads(review["validation_json"] or "{}")
        except (ValueError, TypeError):
            review_validation = {}
        review_dict: dict | None = {
            "status": review["status"],
            "comment": review["comment"],
            "reviewerId": review["reviewer_id"],
            "reviewerName": review["reviewer_name"] if "reviewer_name" in review.keys() else "",
            "reconRunId": review["recon_run_id"] if "recon_run_id" in review.keys() else None,
            "validation": review_validation,
            "version": review["version"],
            "updatedAt": review["updated_at"],
        }
    else:
        review_dict = None
    return {
        "id": row["id"],
        "noticeId": row["notice_id"],
        "agentRunId": row["agent_run_id"],
        "decision": row["decision"],
        "content": row["content"],
        "evidenceIds": evidence_ids,
        "findingIds": finding_ids,
        "ruleVersion": row["rule_version"],
        "status": row["status"],
        "requiresReview": bool(row["requires_review"]),
        "currentVersion": row["current_version"] if "current_version" in row.keys() else 1,
        "reviewStatus": row["review_status"] if "review_status" in row.keys() else "PENDING_REVIEW",
        "review": review_dict,
        "versions": versions_mod.list_versions(row["id"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


@router.get("/agent/status")
async def agent_status():
    return provider_status()


@router.post("/notices/{notice_id}/agent/runs")
async def start_agent_run(notice_id: str):
    if database.get_notice(notice_id) is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    run = orchestrator.run_agent(notice_id)
    if run["status"] == "ERROR" and run.get("error", "").startswith("LLM provider is not configured"):
        raise HTTPException(
            status_code=503,
            detail="Agent unavailable — deterministic reconciliation is still available.",
        )
    return run


@router.get("/notices/{notice_id}/agent/runs")
async def list_runs(notice_id: str):
    try:
        return orchestrator.list_agent_runs(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    try:
        return orchestrator.get_agent_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent run not found.")


@router.post("/notices/{notice_id}/agent/replan")
async def replan(notice_id: str):
    """Re-planning: rerun deterministic reconciliation, then run the agent
    again so it observes the updated state. No state is simulated."""
    if database.get_notice(notice_id) is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    from app.services import reconciliation as recon_service

    try:
        recon = recon_service.run_reconciliation(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    run = orchestrator.run_agent(notice_id)
    return {"reconciliation": recon, "agentRun": run}


@router.get("/notices/{notice_id}/reply-drafts")
async def list_drafts(notice_id: str):
    if database.get_notice(notice_id) is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return [_draft_to_dict(r) for r in database.list_reply_drafts(notice_id)]


@router.get("/notices/{notice_id}/evidence")
async def notice_evidence(notice_id: str):
    from app.agent import tools

    try:
        return tools.tool_get_evidence(notice_id)["data"]
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    row = database.get_reply_draft(draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return _draft_to_dict(row)


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, update: DraftUpdate):
    """Reviewer edits NEVER overwrite history: content edits create a new version."""
    from app.agent import validation as validation_mod
    from app.agent import versions as versions_mod

    row = database.get_reply_draft(draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if update.status is not None and update.status not in ("draft", "in_review", "ready"):
        raise HTTPException(status_code=400, detail="Invalid draft status.")
    if update.content is not None:
        ok, errors = validation_mod.validate_draft(update.content, row["notice_id"])
        if not ok:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        new_version = versions_mod.create_version(draft_id, update.content, "REVIEWER")
        database.create_audit_event(
            row["notice_id"], "REVIEWER", "", "DRAFT_EDITED", "draft", draft_id,
            {"version": new_version["version"]},
        )
    if update.status is not None:
        database.update_reply_draft(draft_id, status=update.status)
    updated = database.get_reply_draft(draft_id)
    assert updated is not None
    return _draft_to_dict(updated)


@router.get("/rules")
async def rule_metadata():
    from app.parsers import gst_rules

    return {"ruleVersion": gst_rules.RULE_VERSION, "sources": gst_rules.SOURCES}
