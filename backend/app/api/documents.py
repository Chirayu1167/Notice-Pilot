import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app import database
from app.parsers.return_parser import ReturnFileError
from app.services import extraction, notice_service, storage

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    error = storage.validate_upload(file.filename or "", content)
    if error:
        raise HTTPException(status_code=400, detail=error)

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    path = storage.save_document(doc_id, file.filename or "upload", content)
    mime = "application/pdf" if path.lower().endswith(".pdf") else "text/plain"
    database.create_document(doc_id, file.filename or "upload", mime, len(content))

    return {
        "document": {
            "id": doc_id,
            "filename": file.filename,
            "mimeType": mime,
            "size": len(content),
            "extractionStatus": "UPLOADED",
        },
        "status": "UPLOADED",
    }


@router.post("/{document_id}/extract")
async def extract_document(document_id: str):
    if database.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        result = notice_service.extract_document(document_id)
        return {
            "documentId": result["document_id"],
            "status": result["status"],
            "text": result["text"],
            "pageCount": result["page_count"],
        }
    except extraction.ExtractionError as e:
        database.update_extraction_status(document_id, "FAILED")
        raise HTTPException(
            status_code=422,
            detail={"status": e.status, "message": str(e)},
        )


@router.get("/{document_id}/text")
async def get_document_text(document_id: str):
    row = database.get_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not row["extracted_text"]:
        raise HTTPException(status_code=404, detail="No extracted text for this document.")
    return {
        "documentId": document_id,
        "status": row["extraction_status"],
        "text": row["extracted_text"],
    }


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    row = database.get_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    from fastapi.responses import FileResponse

    try:
        path = storage.contained_path(
            storage.config.DOCUMENTS_DIR,
            storage.get_document_path(document_id, row["filename"]),
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stored filename.")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Stored file is missing.")
    return FileResponse(path, media_type=row["mime_type"], filename=row["filename"])


@router.post("/{document_id}/return-data")
async def upload_return_data_for_document(
    document_id: str,
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    period: str | None = Form(default=None),
):
    """Alias: attach return data via the source document's notice workspace."""
    from app.services import return_service as return_service_mod

    if database.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    notice = database.get_notice_by_document(document_id)
    if notice is None:
        raise HTTPException(
            status_code=404,
            detail="No notice exists for this document yet. Parse the notice first.",
        )
    try:
        content = await file.read()
        return return_service_mod.upload_return_data(
            notice["id"], file.filename or "upload", content,
            source_hint=source, period=period,
        )
    except ReturnFileError as e:
        raise HTTPException(status_code=422, detail={"status": e.code, "message": str(e)})
