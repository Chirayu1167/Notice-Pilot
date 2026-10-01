"""Phase 6 tests: reviewers, sign-off, comparison, historical truth,
cover-letter export, export validation.

SYNTHETIC DEMO DATA — NOT A REAL GST CASE.
"""

import io
import os

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import database
from app.main import app

client = TestClient(app)

RETURNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "returns")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def return_bytes(name: str) -> bytes:
    with open(os.path.join(RETURNS, name), "rb") as f:
        return f.read()


def fixture_bytes(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def make_notice(fixture_name: str = "synthetic_drc01b_48260.txt") -> dict:
    doc_id = client.post(
        "/api/documents/upload", files={"file": (fixture_name, fixture_bytes(fixture_name))}
    ).json()["document"]["id"]
    return client.post(f"/api/notices/parse/{doc_id}").json()


def upload_return(notice_id: str, name: str):
    return client.post(
        f"/api/notices/{notice_id}/return-data",
        files={"file": (name, return_bytes(name))},
    )


def setup_matched_scenario():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    recon = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert recon["status"] == "MATCHED"
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    assert run["draftId"]
    return notice, recon, run


def get_head(draft_id: str) -> dict:
    return client.get(f"/api/drafts/{draft_id}").json()


def pdf_text(content: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)


# ---------- reviewers ----------

def test_default_demo_reviewer_seeded():
    reviewers = client.get("/api/reviewers").json()
    demo = next((r for r in reviewers if r["id"] == "reviewer_demo"), None)
    assert demo is not None
    assert demo["displayName"] == "Demo Reviewer"
    assert demo["role"] == "REVIEWER"


def test_create_reviewer_and_reject_bad_ids():
    import uuid as _uuid

    name = f"reviewer_case6_{_uuid.uuid4().hex[:8]}"
    res = client.post("/api/reviewers", json={"id": name, "display_name": "Case Six"})
    assert res.status_code == 201
    assert res.json()["displayName"] == "Case Six"
    assert client.post("/api/reviewers", json={"id": name, "display_name": "Dup"}).status_code == 400
    assert client.post("/api/reviewers", json={"id": "BAD ID!", "display_name": "X"}).status_code == 400
    assert client.post("/api/reviewers", json={"id": "ok_id", "display_name": ""}).status_code == 400


def test_review_rejects_unknown_reviewer():
    _, _, run = setup_matched_scenario()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "REQUEST_CHANGES", "comment": "x", "reviewer_id": "ghost"},
    )
    assert res.status_code == 422


# ---------- sign-off ----------

def test_approval_signoff_metadata():
    _, recon, run = setup_matched_scenario()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "APPROVE", "comment": "Verified.", "reviewer_id": "reviewer_demo"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["reviewerId"] == "reviewer_demo"
    assert body["reviewerName"] == "Demo Reviewer"
    assert body["reconRunId"] == recon["id"]
    assert body["validation"]["result"] == "PASS"
    assert body["updatedAt"]
    head = get_head(run["draftId"])
    assert head["review"]["reviewerName"] == "Demo Reviewer"
    assert head["review"]["reconRunId"] == recon["id"]


def test_signoff_immutable_and_not_silently_overwritten():
    _, _, run = setup_matched_scenario()
    first = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "APPROVE", "comment": "First.", "reviewer_id": "reviewer_demo"},
    ).json()
    second = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "APPROVE", "comment": "Second.", "reviewer_id": "reviewer_demo"},
    )
    assert second.status_code == 409  # terminal version: no silent overwrite
    head = get_head(run["draftId"])
    assert head["review"]["comment"] == "First."
    assert head["review"]["reviewerId"] == first["reviewerId"]


# ---------- comparison ----------

def test_compare_versions_content_and_structured():
    _, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    edited = head["content"] + "\nReviewer note: cross-checked totals."
    client.put(f"/api/drafts/{run['draftId']}", json={"content": edited})
    cmp = client.get(f"/api/drafts/{run['draftId']}/compare?from_version=1&to_version=2").json()
    assert cmp["from"] == 1 and cmp["to"] == 2
    assert cmp["hasChanges"] is True
    kinds = {c["kind"] for c in cmp["contentChanges"]}
    assert any("Content change" in k for k in kinds)
    assert any("added" in k for k in kinds)
    fields = {s["field"]: s for s in cmp["structuredChanges"]}
    assert fields["decision"]["changed"] is False
    assert "Evidence / factual change" in fields["evidenceReferences"]["kind"]
    assert "Content change" in fields["decision"]["kind"]


def test_compare_identical_versions_no_changes():
    _, _, run = setup_matched_scenario()
    cmp = client.get(f"/api/drafts/{run['draftId']}/compare?from_version=1&to_version=1")
    assert cmp.status_code == 400
    head = get_head(run["draftId"])
    client.put(f"/api/drafts/{run['draftId']}", json={"content": head["content"]})
    cmp = client.get(f"/api/drafts/{run['draftId']}/compare?from_version=1&to_version=2").json()
    # Identical text still records who created the version; content diff is empty.
    assert cmp["contentChanges"] == []
    created_by = next(s for s in cmp["structuredChanges"] if s["field"] == "createdBy")
    assert created_by["changed"] is True
    assert created_by["from"] == "AGENT" and created_by["to"] == "REVIEWER"


def test_compare_uses_stored_history_not_current():
    _, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    v1_text = head["versions"][0]["content"]
    client.put(f"/api/drafts/{run['draftId']}", json={"content": v1_text + "\nExtra line A."})
    client.put(f"/api/drafts/{run['draftId']}",
               json={"content": v1_text + "\nExtra line A.\nExtra line B."})
    cmp = client.get(f"/api/drafts/{run['draftId']}/compare?from_version=1&to_version=2").json()
    assert not any("Extra line B" in " ".join(c.get("new", [])) for c in cmp["contentChanges"])


def test_compare_unknown_version_404():
    _, _, run = setup_matched_scenario()
    assert client.get(f"/api/drafts/{run['draftId']}/compare?from_version=1&to_version=9").status_code == 404


# ---------- historical truth ----------

def test_historical_version_survives_rerun_and_replan():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/reconciliation")
    run1 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    v1_before = get_head(run1["draftId"])["versions"][0]
    assert v1_before["reconSnapshot"]["status"] == "PARTIAL"

    # New evidence + rerun + replan (creates a NEW draft on the new state).
    upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    replan = client.post(f"/api/notices/{notice['id']}/agent/replan").json()
    assert replan["reconciliation"]["status"] == "MATCHED"
    new_draft_id = replan["agentRun"]["draftId"]
    assert new_draft_id != run1["draftId"]

    # The old draft's v1 is untouched by everything that followed.
    v1_after = next(v for v in get_head(run1["draftId"])["versions"] if v["version"] == 1)
    assert v1_after["content"] == v1_before["content"]
    assert v1_after["reconSnapshot"] == v1_before["reconSnapshot"]
    assert v1_after["reconSnapshot"]["status"] == "PARTIAL"
    assert v1_after["reconSnapshot"]["unexplainedAmount"] == 6160.0

    # Editing the old draft is honestly rejected: its citations are stale
    # after the rerun (new finding IDs), so history cannot silently mutate.
    head = get_head(run1["draftId"])
    stale_edit = client.put(
        f"/api/drafts/{run1['draftId']}", json={"content": head["content"] + "\nPost-replan note."}
    )
    assert stale_edit.status_code == 422

    # The new draft snapshots the new truth.
    new_head = get_head(new_draft_id)
    assert new_head["versions"][0]["reconSnapshot"]["status"] == "MATCHED"
    assert new_head["versions"][0]["reconSnapshot"]["unexplainedAmount"] == 0.0


def test_historical_pdf_keeps_original_numbers_after_rerun():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/reconciliation")
    run1 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/agent/replan")
    text = pdf_text(client.get(f"/api/drafts/{run1['draftId']}/pdf?version=1").content)
    assert "6,160.00" in text
    assert "42,100.00" in text


# ---------- cover letter + export validation ----------

def test_cover_letter_pending_shows_draft_banner():
    _, _, run = setup_matched_scenario()
    res = client.get(f"/api/drafts/{run['draftId']}/cover-letter")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    text = pdf_text(res.content)
    assert "DRAFT" in text and "HUMAN REVIEW REQUIRED" in text
    assert "Prepared by NoticePilot for human review and submission." in text
    assert "does not submit this document" in text
    assert "48,260.00" in text
    assert "DRC-01B/2025-26/SYN/5005" in text
    for banned in ("FILED", "SUBMITTED", "ACCEPTED BY GST", "OFFICIALLY RESOLVED"):
        assert banned not in text


def test_cover_letter_approved_shows_reviewed_banner():
    _, _, run = setup_matched_scenario()
    client.post(f"/api/drafts/{run['draftId']}/review",
                json={"action": "APPROVE", "comment": "ok", "reviewer_id": "reviewer_demo"})
    text = pdf_text(client.get(f"/api/drafts/{run['draftId']}/cover-letter").content)
    assert "READY FOR HUMAN SUBMISSION" in text
    assert "Demo Reviewer" in text


def test_export_rejects_stale_snapshot():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/reconciliation")
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    # Remove the snapshot reconciliation run (draft survives): export must
    # refuse to render a document it can no longer verify.
    conn = database.connect()
    try:
        conn.execute("DELETE FROM findings WHERE notice_id = ?", (notice["id"],))
        conn.execute("DELETE FROM reconciliation_runs WHERE notice_id = ?", (notice["id"],))
        conn.commit()
    finally:
        conn.close()
    res = client.get(f"/api/drafts/{run['draftId']}/cover-letter")
    assert res.status_code in (404, 422)
    assert "snapshot" in res.json()["detail"].lower() or res.status_code == 404


def test_export_unknown_version_404():
    _, _, run = setup_matched_scenario()
    assert client.get(f"/api/drafts/{run['draftId']}/cover-letter?version=99").status_code == 404
