import os

import pytest

from app.services import extraction
from tests.conftest import fixture_path, make_pdf


def test_extract_txt():
    result = extraction.extract_text(fixture_path("synthetic_drc01b.txt"), "text/plain")
    assert "DRC-01B" in result["text"]
    assert len(result["pages"]) >= 1


def test_extract_txt_fallback_encoding(tmp_path):
    path = tmp_path / "latin.txt"
    path.write_bytes("Café notice Rs. 100".encode("latin-1"))
    result = extraction.extract_text(str(path), "text/plain")
    assert "Rs. 100" in result["text"]


def test_extract_pdf(drc01b_pdf):
    result = extraction.extract_text(drc01b_pdf, "application/pdf")
    assert "DRC-01B" in result["text"]
    assert len(result["pages"]) == 1


def test_extract_scanned_pdf_requires_ocr(scanned_pdf):
    with pytest.raises(extraction.ExtractionError) as exc:
        extraction.extract_text(scanned_pdf, "application/pdf")
    assert exc.value.status == "OCR_REQUIRED"
    assert "OCR" in str(exc.value)


def test_extract_empty_txt():
    with pytest.raises(extraction.ExtractionError, match="empty"):
        extraction.extract_text(fixture_path("empty.txt"), "text/plain")


def test_extract_malformed_pdf(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-not-a-real-pdf")
    with pytest.raises(extraction.ExtractionError, match="Could not read"):
        extraction.extract_text(str(path), "application/pdf")


def test_extract_pdf_preserves_page_boundaries(tmp_path):
    path = tmp_path / "multi.pdf"
    doc_pages = ["Page one text", "Page two text"]
    import pymupdf

    doc = pymupdf.open()
    for line in doc_pages:
        page = doc.new_page()
        page.insert_text((72, 72), line, fontsize=11)
    doc.save(str(path))
    doc.close()
    result = extraction.extract_text(str(path), "application/pdf")
    assert len(result["pages"]) == 2
    assert "Page two" in result["text"]
