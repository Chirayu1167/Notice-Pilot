import io
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import fixture_path

client = TestClient(app)


def upload_file(name: str, content: bytes | None = None, filename: str | None = None):
    if content is None:
        with open(fixture_path(name), "rb") as f:
            content = f.read()
    return client.post(
        "/api/documents/upload",
        files={"file": (filename or name, content)},
    )


def test_upload_txt():
    res = upload_file("synthetic_drc01b.txt")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "UPLOADED"
    assert body["document"]["filename"] == "synthetic_drc01b.txt"
    assert body["document"]["mimeType"] == "text/plain"
    assert body["document"]["size"] > 0


def test_upload_pdf(drc01b_pdf):
    with open(drc01b_pdf, "rb") as f:
        res = client.post(
            "/api/documents/upload",
            files={"file": ("synthetic_drc01b.pdf", f.read())},
        )
    assert res.status_code == 200
    assert res.json()["document"]["mimeType"] == "application/pdf"


def test_reject_unsupported_file():
    res = upload_file("malware.exe", b"MZ\x90\x00 fake exe", "malware.exe")
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_reject_zip_renamed_as_txt():
    res = upload_file("fake.txt", b"PK\x03\x04 zip content", "fake.txt")
    assert res.status_code == 400
    assert "Invalid text file" in res.json()["detail"]


def test_reject_image():
    res = upload_file("photo.jpg", b"\xff\xd8\xff\xe0 jpeg bytes", "photo.jpg")
    assert res.status_code == 400


def test_reject_oversized_file(tmp_path):
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (11 * 1024 * 1024))
    with open(big, "rb") as f:
        res = client.post("/api/documents/upload", files={"file": ("big.txt", f.read())})
    assert res.status_code == 400
    assert "too large" in res.json()["detail"]


def test_extract_endpoint():
    doc_id = upload_file("synthetic_drc01b.txt").json()["document"]["id"]
    res = client.post(f"/api/documents/{doc_id}/extract")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "EXTRACTED"
    assert "DRC-01B" in body["text"]


def test_extract_scanned_pdf_returns_ocr_required(scanned_pdf):
    with open(scanned_pdf, "rb") as f:
        doc_id = client.post(
            "/api/documents/upload",
            files={"file": ("scanned.pdf", f.read())},
        ).json()["document"]["id"]
    res = client.post(f"/api/documents/{doc_id}/extract")
    assert res.status_code == 422
    assert res.json()["detail"]["status"] == "OCR_REQUIRED"


def test_parse_pipeline_creates_notice():
    doc_id = upload_file("synthetic_drc01b.txt").json()["document"]["id"]
    res = client.post(f"/api/notices/parse/{doc_id}")
    assert res.status_code == 200
    notice = res.json()
    assert notice["status"] == "VALID"
    assert notice["noticeType"] == "DRC-01B"
    assert notice["gstin"] == "99SYNTA0000A1Z9"
    assert notice["taxPeriod"] == "2024-25"
    assert notice["differenceAmount"] == 150000.0
    assert notice["dueDate"] == "2025-02-14"


def test_parse_unrelated_document_is_unsupported():
    doc_id = upload_file("unrelated.txt").json()["document"]["id"]
    res = client.post(f"/api/notices/parse/{doc_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "UNSUPPORTED"


def test_parse_empty_document_fails_honestly():
    doc_id = upload_file("empty.txt").json()["document"]["id"]
    res = client.post(f"/api/notices/parse/{doc_id}")
    assert res.status_code == 422
    assert "empty" in res.json()["detail"]["message"].lower()


def test_list_and_get_notice():
    doc_id = upload_file("synthetic_drc01c.txt").json()["document"]["id"]
    notice_id = client.post(f"/api/notices/parse/{doc_id}").json()["id"]

    listing = client.get("/api/notices").json()
    assert any(n["id"] == notice_id for n in listing)

    fetched = client.get(f"/api/notices/{notice_id}").json()
    assert fetched["noticeType"] == "DRC-01C"
    assert fetched["filename"] == "synthetic_drc01c.txt"


def test_get_missing_notice_404():
    res = client.get("/api/notices/notice_doesnotexist")
    assert res.status_code == 404


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}
