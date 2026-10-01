"""Demo workspace tests (Phase 6.9): reset determinism, user-data safety,
supplement flow, disabled mode.

SYNTHETIC DEMO DATA — NOT A REAL GST CASE.
"""

import os

from fastapi.testclient import TestClient

from app import database
from app.main import app

client = TestClient(app)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_bytes(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def make_user_notice() -> dict:
    """A NON-demo notice that reset must never touch."""
    content = (
        "GOODS AND SERVICES TAX — RECONCILIATION STATEMENT\n"
        "Form DRC-01B (Reconciliation of Outward Supplies)\n"
        "Notice No. : DRC-01B/2025-26/USER/0007\n"
        "GSTIN: 99SYNTA0000A1Z9\n"
        "Subject: Differences for tax period 2025-06.\n"
        "Difference of Rs. 2,000.00\n"
        "You are required to submit a reply explaining the difference of Rs. 2,000.00.\n"
        "Due date: 13/09/2025\n"
    ).encode()
    doc_id = client.post(
        "/api/documents/upload", files={"file": ("user_notice.txt", content)}
    ).json()["document"]["id"]
    return client.post(f"/api/notices/parse/{doc_id}").json()


def test_demo_describe_labels_synthetic():
    body = client.get("/api/demo/describe").json()
    assert "SYNTHETIC DEMO DATA" in body["label"]
    assert body["noticeNumber"] == "DRC-01B/2025-26/SYN/5005"


def test_demo_reset_builds_initial_mismatch():
    body = client.post("/api/demo/reset").json()
    assert "SYNTHETIC DEMO DATA" in body["label"]
    assert body["stage"] == "initial-mismatch"
    assert body["reconciliation"]["status"] == "PARTIAL"
    assert body["reconciliation"]["noticeDifference"] == 48260.0
    assert body["reconciliation"]["explainedAmount"] == 42100.0
    assert body["reconciliation"]["unexplainedAmount"] == 6160.0
    assert body["agentRun"]["decision"] == "INSUFFICIENT_EVIDENCE"
    assert body["draftId"]


def test_demo_reset_is_deterministic():
    first = client.post("/api/demo/reset").json()
    second = client.post("/api/demo/reset").json()
    assert first["reconciliation"] == second["reconciliation"]
    assert first["agentRun"]["decision"] == second["agentRun"]["decision"]
    # Exactly one demo notice workspace exists afterwards.
    rows = database.find_demo_notices(
        ["DRC-01B/2025-26/SYN/5005"], ["synthetic_drc01b_48260.txt"])
    assert len(rows) == 1
    assert rows[0]["id"] == second["noticeId"]


def test_demo_reset_preserves_user_data():
    user = make_user_notice()
    assert user["noticeNumber"] == "DRC-01B/2025-26/USER/0007"
    client.post("/api/demo/reset")
    fetched = client.get(f"/api/notices/{user['id']}").json()
    assert fetched["noticeNumber"] == "DRC-01B/2025-26/USER/0007"
    # User audit trail untouched.
    assert database.get_document(fetched["documentId"]) is not None


def test_demo_supplement_reconciles_and_replans():
    reset = client.post("/api/demo/reset").json()
    body = client.post(
        "/api/demo/supplement", params={"notice_id": reset["noticeId"]}
    ).json()
    assert body["stage"] == "reconciled"
    assert body["reconciliation"]["status"] == "MATCHED"
    assert body["reconciliation"]["unexplainedAmount"] == 0.0
    assert body["agentRun"]["decision"] == "CONTEST"
    assert body["draftId"]


def test_demo_supplement_rejects_non_demo_notice():
    user = make_user_notice()
    res = client.post("/api/demo/supplement", params={"notice_id": user["id"]})
    assert res.status_code == 400
    res = client.post("/api/demo/supplement", params={"notice_id": "notice_nope"})
    assert res.status_code == 404


def test_demo_disabled_mode(monkeypatch):
    monkeypatch.setenv("DEMO_ENABLED", "0")
    assert client.post("/api/demo/reset").status_code == 403
    assert client.get("/api/demo/describe").status_code == 403
    monkeypatch.setenv("DEMO_ENABLED", "1")
    assert client.get("/api/demo/describe").status_code == 200
