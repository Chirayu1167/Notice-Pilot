"""Human review API (Phase 5). Review-gated workflow over versioned drafts.

APPROVE / REQUEST_CHANGES / REJECT with server-side validation. Approved or
rejected versions are immutable; further edits create new versions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database
from app.agent import reviewers as reviewers_mod
from app.agent import tools, validation

router = APIRouter()

REVIEW_ACTIONS = ("APPROVE", "REQUEST_CHANGES", "REJECT")
TERMINAL_STATUSES = ("APPROVED", "REJECTED")


class ReviewRequest(BaseModel):
    action: str
    comment: str = ""
    reviewer_id: str = "reviewer_demo"
    reviewer_name: str = ""


class ReviewerCreate(BaseModel):
    id: str
    display_name: str


@router.get("/reviewers")
async def list_reviewers():
    return reviewers_mod.list_reviewers()


@router.post("/reviewers", status_code=201)
async def create_reviewer(req: ReviewerCreate):
    try:
        return reviewers_mod.create_reviewer(req.id, req.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _require_draft(draft_id: str):
    row = database.get_reply_draft(draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return row


def _approval_blockers(head) -> list[str]:
    """Server-side approval guardrails. Returns blocking reasons (empty = ok)."""
    blockers: list[str] = []
    notice_id = head["notice_id"]
    try:
        from app.services import reconciliation as recon_service

        recon = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        recon = None
    if recon is None:
        blockers.append("No reconciliation run exists for this notice.")
        return blockers
    if (recon.get("status") or "").upper() == "ERROR":
        blockers.append("Reconciliation is in an error state.")
    missing = tools.build_missing_evidence(notice_id)
    if missing:
        reasons = [m.reason if hasattr(m, "reason") else m.get("reason", "") for m in missing]
        blockers.append(f"Required evidence is missing: {'; '.join(reasons)}.")
    ok, errors = validation.validate_draft(head["content"], notice_id)
    if not ok:
        blockers.append(f"Draft validation failed: {'; '.join(errors)}.")
    valid_findings = {f["id"] for f in recon.get("findings") or []}
    import json as _json

    try:
        head_findings = set(_json.loads(head["finding_ids_json"] or "[]"))
    except (ValueError, TypeError):
        head_findings = set()
    stale = sorted(head_findings - valid_findings)
    if stale:
        blockers.append(f"Draft references stale/unknown findings: {', '.join(stale)}.")
    return blockers


@router.get("/notices/{notice_id}/review")
async def review_state(notice_id: str):
    if database.get_notice(notice_id) is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    drafts = database.list_reply_drafts(notice_id)
    if not drafts:
        return {"noticeId": notice_id, "draftId": None, "review": None, "versions": []}
    from app.api.agent import _draft_to_dict

    head = _draft_to_dict(drafts[0])
    return {
        "noticeId": notice_id,
        "draftId": head["id"],
        "review": head["review"],
        "reviewStatus": head["reviewStatus"],
        "currentVersion": head["currentVersion"],
        "versions": head["versions"],
    }


@router.post("/drafts/{draft_id}/review")
async def review_action(draft_id: str, req: ReviewRequest):
    head = _require_draft(draft_id)
    action = (req.action or "").upper()
    if action not in REVIEW_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid action '{req.action}'.")
    comment = (req.comment or "").strip()
    if action in ("REQUEST_CHANGES", "REJECT") and not comment:
        raise HTTPException(status_code=422, detail=f"{action} requires a comment.")
    try:
        reviewer = reviewers_mod.get_reviewer_or_raise((req.reviewer_id or "").strip() or "reviewer_demo")
    except KeyError:
        raise HTTPException(
            status_code=422, detail=f"Unknown reviewer '{req.reviewer_id}'. Pick a demo reviewer identity."
        )

    from app.agent import versions as versions_mod

    versions = versions_mod.list_versions(draft_id)
    current = next((v for v in versions if v["version"] == (head["current_version"] or 1)), None)
    if current is None:
        raise HTTPException(status_code=409, detail="Current draft version not found.")
    if current["reviewStatus"] in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Version {current['version']} is {current['reviewStatus']} and immutable. "
            "Create a new version to continue.",
        )

    validation_result: dict = {"result": "NOT_RUN"}
    recon_run_id: str | None = None
    if action == "APPROVE":
        blockers = _approval_blockers(head)
        if blockers:
            raise HTTPException(status_code=422, detail="; ".join(blockers))
        new_status = "APPROVED"
        # Explicit sign-off metadata, captured once and never edited.
        from app.services import reconciliation as recon_service

        latest = recon_service.get_latest_reconciliation(head["notice_id"])
        recon_run_id = latest["id"]
        ok, _ = validation.validate_draft(head["content"], head["notice_id"])
        validation_result = {
            "result": "PASS" if ok else "FAIL",
            "ruleVersion": latest.get("ruleVersion"),
            "reconRunId": recon_run_id,
            "reconStatus": latest.get("status"),
        }
    elif action == "REQUEST_CHANGES":
        new_status = "CHANGES_REQUESTED"
    else:
        new_status = "REJECTED"

    database.set_version_review_status(current["id"], new_status)
    review_id = database.upsert_review(
        head["notice_id"], draft_id, current["version"],
        reviewer["id"], new_status, comment,
        reviewer_name=reviewer["displayName"],
        recon_run_id=recon_run_id,
        validation=validation_result,
    )
    database.create_audit_event(
        head["notice_id"], "REVIEWER", reviewer["id"], new_status,
        "draft", draft_id,
        {"version": current["version"], "comment": comment,
         "reviewerName": reviewer["displayName"]},
    )
    review = database.get_review_by_draft(draft_id)
    assert review is not None
    return {
        "reviewId": review_id,
        "draftId": draft_id,
        "version": current["version"],
        "status": new_status,
        "comment": comment,
        "reviewerId": reviewer["id"],
        "reviewerName": reviewer["displayName"],
        "reconRunId": recon_run_id,
        "validation": validation_result,
        "updatedAt": review["updated_at"],
    }


def _audit_to_dict(e) -> dict:
    import json as _json

    try:
        metadata = _json.loads(e["metadata_json"] or "{}")
    except (ValueError, TypeError):
        metadata = {}
    return {
        "id": e["id"],
        "noticeId": e["notice_id"],
        "actorType": e["actor_type"],
        "actorId": e["actor_id"],
        "action": e["action"],
        "entityType": e["entity_type"],
        "entityId": e["entity_id"],
        "metadata": metadata,
        "createdAt": e["created_at"],
    }


@router.get("/notices/{notice_id}/audit")
async def notice_audit(notice_id: str):
    if database.get_notice(notice_id) is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return [_audit_to_dict(e) for e in database.list_audit_events(notice_id)]


@router.get("/drafts/{draft_id}/audit")
async def draft_audit(draft_id: str):
    _require_draft(draft_id)
    return [_audit_to_dict(e) for e in database.list_audit_events_for_entity("draft", draft_id)]


@router.get("/drafts/{draft_id}/versions")
async def draft_versions(draft_id: str):
    from app.agent import versions as versions_mod

    _require_draft(draft_id)
    try:
        return versions_mod.list_versions(draft_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Draft not found.")


@router.get("/drafts/{draft_id}/compare")
async def draft_compare(draft_id: str, from_version: int, to_version: int):
    from app.agent import compare as compare_mod

    _require_draft(draft_id)
    if from_version == to_version:
        raise HTTPException(status_code=400, detail="Pick two different versions to compare.")
    try:
        return compare_mod.compare_versions(draft_id, from_version, to_version)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/drafts/{draft_id}/pdf")
async def draft_pdf(draft_id: str, version: int | None = None):
    from fastapi.responses import Response

    from app.agent import export_validation as export_mod
    from app.agent import pdf as pdf_mod

    head = database.get_reply_draft(draft_id)
    if head is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    ok, errors, _ = export_mod.validate_version_for_export(draft_id, version)
    if not ok:
        if any("not found" in e.lower() for e in errors):
            raise HTTPException(status_code=404, detail="; ".join(errors))
        raise HTTPException(status_code=422, detail="; ".join(errors))
    try:
        packet = pdf_mod.build_review_packet(draft_id, version)
    except (KeyError, LookupError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    content = pdf_mod.render_pdf(packet)
    database.create_audit_event(
        head["notice_id"], "REVIEWER", "", "PDF_EXPORTED", "draft", draft_id,
        {"version": packet["version"]},
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{draft_id}-v{packet['version']}.pdf\""},
    )


@router.get("/drafts/{draft_id}/cover-letter")
async def draft_cover_letter(draft_id: str, version: int | None = None):
    """Portal-ready cover letter: a human-carried document, NOT a filing."""
    from fastapi.responses import Response

    from app.agent import pdf as pdf_mod

    head = database.get_reply_draft(draft_id)
    if head is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    try:
        packet = pdf_mod.build_cover_packet(draft_id, version)
    except (KeyError, LookupError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    content = pdf_mod.render_cover_pdf(packet)
    database.create_audit_event(
        head["notice_id"], "REVIEWER", "", "COVER_LETTER_EXPORTED", "draft", draft_id,
        {"version": packet["version"], "reviewStatus": packet["reviewStatus"]},
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{draft_id}-v{packet['version']}-cover.pdf\""},
    )
