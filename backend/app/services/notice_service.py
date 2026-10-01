import uuid

from app import database
from app.parsers import notice_parser, validation
from app.services import extraction, storage


def extract_document(document_id: str) -> dict:
    row = database.get_document(document_id)
    if row is None:
        raise KeyError(document_id)
    path = storage.get_document_path(document_id, row["filename"])
    result = extraction.extract_text(path, row["mime_type"])
    database.store_extracted_text(document_id, result["text"])
    return {
        "document_id": document_id,
        "status": "EXTRACTED",
        "text": result["text"],
        "page_count": len(result["pages"]),
    }


def parse_document(document_id: str) -> dict:
    row = database.get_document(document_id)
    if row is None:
        raise KeyError(document_id)

    text = database.get_extracted_text(document_id)
    if text is None:
        path = storage.get_document_path(document_id, row["filename"])
        text = extraction.extract_text(path, row["mime_type"])["text"]
        database.store_extracted_text(document_id, text)

    parsed = notice_parser.parse_notice(text)
    status = validation.validate(parsed, text)

    notice_id = f"notice_{uuid.uuid4().hex[:12]}"
    database.create_notice(notice_id, document_id, parsed, status)
    return get_notice(notice_id)


def get_notice(notice_id: str) -> dict:
    row = database.get_notice(notice_id)
    if row is None:
        raise KeyError(notice_id)
    return _notice_to_dict(row)


def list_notices() -> list[dict]:
    return [_notice_to_dict(row) for row in database.list_notices()]


def _camel(key: str) -> str:
    parts = key.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


def _notice_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "documentId": row["document_id"],
        "noticeNumber": row["notice_number"],
        "noticeType": row["notice_type"],
        "gstin": row["gstin"],
        "taxPeriod": row["tax_period"],
        "issueDate": row["issue_date"],
        "dueDate": row["due_date"],
        "differenceAmount": row["difference_amount"],
        "requestedAction": row["requested_action"],
        "status": row["status"],
        "filename": row["filename"],
        "mimeType": row["mime_type"],
        "documentSize": row["document_size"],
        "extractionStatus": row["extraction_status"],
    }
