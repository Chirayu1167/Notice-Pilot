from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.parsers.return_parser import ReturnFileError
from app.services import reconciliation as recon_service
from app.services import return_service

router = APIRouter()


@router.post("/{notice_id}/return-data")
async def upload_return_data(
    notice_id: str,
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    period: str | None = Form(default=None),
):
    try:
        content = await file.read()
        result = return_service.upload_return_data(
            notice_id, file.filename or "upload", content,
            source_hint=source, period=period,
        )
        from app import database as _db

        _db.create_audit_event(
            notice_id, "SYSTEM", "", "RETURN_UPLOADED", "return_document", result["id"],
            {"source": result.get("source"), "filename": result.get("filename")},
        )
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    except ReturnFileError as e:
        raise HTTPException(status_code=422, detail={"status": e.code, "message": str(e)})


@router.get("/{notice_id}/return-data")
async def list_return_data(notice_id: str):
    try:
        return return_service.list_return_data(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")


@router.get("/{notice_id}/return-data/{return_id}/download")
async def download_return_file(notice_id: str, return_id: str):
    from fastapi.responses import FileResponse

    try:
        path, filename, mime = return_service.get_return_file(notice_id, return_id)
        return FileResponse(path, media_type=mime, filename=filename)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    except LookupError:
        raise HTTPException(status_code=404, detail="Return document not found.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stored filename.")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Original file was not stored for this upload. Re-upload the return file.",
        )


@router.get("/{notice_id}/return-rows")
async def get_return_rows(notice_id: str, ids: str = ""):
    from app.services import lineage as lineage_service

    try:
        row_ids = [x.strip() for x in (ids or "").split(",") if x.strip()]
        if not row_ids:
            raise HTTPException(status_code=400, detail="Query parameter 'ids' is required.")
        return lineage_service.get_return_rows(notice_id, row_ids)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")


@router.post("/{notice_id}/reconciliation")
async def run_reconciliation(notice_id: str):
    try:
        result = recon_service.run_reconciliation(notice_id)
        from app import database as _db

        _db.create_audit_event(
            notice_id, "SYSTEM", "", "RECONCILIATION_COMPLETED", "reconciliation_run",
            result["id"], {"status": result.get("status")},
        )
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")


@router.get("/{notice_id}/reconciliation")
async def get_reconciliation(notice_id: str):
    try:
        return recon_service.get_latest_reconciliation(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
