import pymupdf


class ExtractionError(Exception):
    def __init__(self, message: str, status: str = "FAILED"):
        super().__init__(message)
        self.status = status


def extract_text(path: str, mime_type: str) -> dict:
    if mime_type == "application/pdf":
        return _extract_pdf(path)
    return _extract_txt(path)


def _extract_txt(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.strip():
        raise ExtractionError("Document is empty.")
    text = None
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ExtractionError("Could not decode text document.")
    if not text.strip():
        raise ExtractionError("Document is empty.")
    pages = [page for page in text.split("\f") if page.strip()]
    return {"text": text, "pages": pages or [text]}


def _extract_pdf(path: str) -> dict:
    try:
        doc = pymupdf.open(path)
    except Exception:
        raise ExtractionError("Could not read PDF file. The file may be corrupted.")
    try:
        if doc.is_encrypted:
            if not doc.authenticate(""):
                raise ExtractionError("PDF is password protected.")
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()
    text = "\n".join(pages)
    if not text.strip():
        raise ExtractionError(
            "Scanned documents require OCR, which is not enabled yet.",
            status="OCR_REQUIRED",
        )
    return {"text": text, "pages": pages}
