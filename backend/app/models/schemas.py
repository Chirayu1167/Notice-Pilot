from typing import Optional

from pydantic import BaseModel


class Document(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    extraction_status: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    document: Document
    status: str = "UPLOADED"


class ExtractionResponse(BaseModel):
    document_id: str
    status: str
    text: Optional[str] = None
    page_count: Optional[int] = None
    message: Optional[str] = None


class Notice(BaseModel):
    id: str
    document_id: str
    notice_number: Optional[str] = None
    notice_type: Optional[str] = None
    gstin: Optional[str] = None
    tax_period: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    difference_amount: Optional[float] = None
    requested_action: Optional[str] = None
    status: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    document_size: Optional[int] = None
    extraction_status: Optional[str] = None
