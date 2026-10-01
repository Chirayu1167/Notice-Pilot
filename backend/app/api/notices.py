from fastapi import APIRouter, HTTPException

from app import database
from app.services import extraction, notice_service

router = APIRouter()


@router.post("/parse/{document_id}")
async def parse_notice(document_id: str):
    if database.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        notice = notice_service.parse_document(document_id)
        database.create_audit_event(
            notice["id"], "SYSTEM", "", "DOCUMENT_UPLOADED", "document", document_id,
            {"filename": notice.get("filename")},
        )
        return notice
    except extraction.ExtractionError as e:
        database.update_extraction_status(document_id, "FAILED")
        raise HTTPException(
            status_code=422,
            detail={"status": e.status, "message": str(e)},
        )


@router.get("/")
async def list_notices():
    return notice_service.list_notices()


@router.get("/{notice_id}")
async def get_notice(notice_id: str):
    try:
        return notice_service.get_notice(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
