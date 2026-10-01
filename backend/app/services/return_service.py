"""Return-data upload service (Phase 2). Deterministic, no LLM."""

import json
import os
import uuid

from app import config, database
from app.parsers import normalize as n
from app.parsers.return_parser import ReturnFileError, parse_return_file
from app.services import storage


def _mime_for(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".csv":
        return "text/csv"
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload_return_data(
    notice_id: str,
    filename: str,
    content: bytes,
    source_hint: str | None = None,
    period: str | None = None,
) -> dict:
    notice_row = database.get_notice(notice_id)
    if notice_row is None:
        raise KeyError(notice_id)
    if len(content) > config.RETURN_MAX_FILE_SIZE:
        raise ReturnFileError("File too large. Maximum size is 10 MB.", code="TOO_LARGE")

    parsed = parse_return_file(
        filename, content,
        source_hint=source_hint, period=period,
        max_rows=config.RETURN_MAX_ROWS,
    )
    source = parsed["source"]
    return_period = parsed["period"]
    notice_period = notice_row["tax_period"]
    period_status = n.compare_period(notice_period, return_period)

    return_id = f"ret_{uuid.uuid4().hex[:12]}"
    database.create_return_document(
        return_id, notice_id, source, return_period, period_status,
        filename, _mime_for(filename), len(content), len(parsed["rows"]),
    )
    # SOURCE DOCUMENT -> ORIGINAL FILE: keep the exact uploaded bytes.
    storage.save_return_file(return_id, filename, content)
    db_rows = []
    for i, r in enumerate(parsed["rows"]):
        db_rows.append(
            {
                "id": f"{return_id}-r{i + 1:04d}",
                "return_id": return_id,
                "notice_id": notice_id,
                "source": r["source"],
                "period": r.get("period"),
                "supplier_gstin": r.get("supplier_gstin"),
                "recipient_gstin": r.get("recipient_gstin"),
                "invoice_number": r.get("invoice_number"),
                "invoice_date": r.get("invoice_date"),
                "taxable_value": r.get("taxable_value"),
                "igst": r.get("igst"),
                "cgst": r.get("cgst"),
                "sgst": r.get("sgst"),
                "cess": r.get("cess"),
                "total_tax": r.get("total_tax"),
                "credit_debit_note": r.get("credit_debit_note"),
                "raw_json": json.dumps(r.get("raw") or {}, default=str),
            }
        )
    database.insert_return_rows(db_rows)

    return {
        "id": return_id,
        "noticeId": notice_id,
        "source": source,
        "period": return_period,
        "periodStatus": period_status,
        "filename": filename,
        "rowCount": len(db_rows),
        "status": "READY",
        "downloadUrl": f"/api/notices/{notice_id}/return-data/{return_id}/download",
    }


def list_return_data(notice_id: str) -> list[dict]:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    return [
        {
            "id": r["id"],
            "noticeId": r["notice_id"],
            "source": r["source"],
            "period": r["period"],
            "periodStatus": r["period_status"],
            "filename": r["filename"],
            "rowCount": r["row_count"],
            "status": r["status"],
            "downloadUrl": f"/api/notices/{r['notice_id']}/return-data/{r['id']}/download",
        }
        for r in database.list_return_documents(notice_id)
    ]


def get_return_file(notice_id: str, return_id: str) -> tuple[str, str, str]:
    """Return (path, filename, mime_type) for the ORIGINAL uploaded return file."""
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    ret = database.get_return_document(return_id)
    if ret is None or ret["notice_id"] != notice_id:
        raise LookupError(return_id)
    path = storage.contained_path(
        storage.config.RETURNS_DIR,
        storage.get_return_file_path(return_id, ret["filename"]),
    )
    if not os.path.exists(path):
        raise FileNotFoundError(return_id)
    return path, ret["filename"], ret["mime_type"]
