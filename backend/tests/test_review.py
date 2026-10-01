"""Phase 5 tests: versioned drafts, human review, audit trail, validation, PDF.

SYNTHETIC DEMO DATA — NOT A REAL GST CASE.
"""

import os
import re

from fastapi.testclient import TestClient

from app import database
from app.agent import validation
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
    """Fully reconciled synthetic case: MATCHED, no missing evidence."""
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


# ---------- draft versioning ----------

def test_v1_created_with_draft():
    _, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    assert head["currentVersion"] == 1
    assert len(head["versions"]) == 1
    v1 = head["versions"][0]
    assert v1["version"] == 1 and v1["createdBy"] == "AGENT"
    assert v1["parentVersionId"] is None
    assert v1["reviewStatus"] == "PENDING_REVIEW"
    assert v1["reconSnapshot"]["ran"] is True
    assert v1["reconSnapshot"]["status"] == "MATCHED"


def test_edit_creates_v2_and_preserves_v1():
    _, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    v1_content = head["versions"][0]["content"]
    edited = v1_content + "\nReviewer note: figures verified against uploaded records."
    res = client.put(f"/api/drafts/{run['draftId']}", json={"content": edited})
    assert res.status_code == 200
    head2 = res.json()
    assert head2["currentVersion"] == 2
    assert head2["content"] == edited
    v1 = next(v for v in head2["versions"] if v["version"] == 1)
    v2 = next(v for v in head2["versions"] if v["version"] == 2)
    assert v1["content"] == v1_content  # immutable v1
    assert v2["parentVersionId"] == v1["id"]
    assert v2["createdBy"] == "REVIEWER"
    assert [v["version"] for v in head2["versions"]] == [1, 2]


def test_version_ordering_multiple_edits():
    _, _, run = setup_matched_scenario()
    base = get_head(run["draftId"])["content"]
    for i in range(3):
        res = client.put(
            f"/api/drafts/{run['draftId']}", json={"content": base + f"\nNote {i}."}
        )
        assert res.status_code == 200
    head = get_head(run["draftId"])
    assert head["currentVersion"] == 4
    assert [v["version"] for v in head["versions"]] == [1, 2, 3, 4]


# ---------- review ----------

def test_request_changes_requires_comment():
    _, _, run = setup_matched_scenario()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "REQUEST_CHANGES", "comment": ""},
    )
    assert res.status_code == 422
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "REQUEST_CHANGES", "comment": "Please clarify the remaining difference."},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "CHANGES_REQUESTED"


def test_reject_requires_comment_and_marks_version():
    _, _, run = setup_matched_scenario()
    assert client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "REJECT", "comment": ""}
    ).status_code == 422
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "REJECT", "comment": "Records do not support this response."},
    )
    assert res.status_code == 200
    head = get_head(run["draftId"])
    assert head["reviewStatus"] == "REJECTED"
    assert head["versions"][0]["reviewStatus"] == "REJECTED"


def test_approve_matched_draft():
    _, _, run = setup_matched_scenario()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "APPROVE", "comment": "Verified against uploaded records."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "APPROVED"
    head = get_head(run["draftId"])
    assert head["reviewStatus"] == "APPROVED"
    assert head["review"]["comment"] == "Verified against uploaded records."


def test_approve_blocked_with_missing_evidence():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/reconciliation")
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "APPROVE", "comment": "ok"}
    )
    assert res.status_code == 422
    assert "missing" in res.json()["detail"].lower()


def test_approved_version_immutable_new_version_pending():
    _, _, run = setup_matched_scenario()
    client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "APPROVE", "comment": "ok"}
    )
    # Second approval on the same version is rejected: it is immutable.
    res = client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "APPROVE", "comment": "again"}
    )
    assert res.status_code == 409
    # Editing creates v2 as PENDING_REVIEW; v1 stays APPROVED.
    head = get_head(run["draftId"])
    edited = head["content"] + "\nReviewer note: post-approval clarification."
    res = client.put(f"/api/drafts/{run['draftId']}", json={"content": edited})
    assert res.status_code == 200
    head2 = res.json()
    assert head2["currentVersion"] == 2
    assert head2["reviewStatus"] == "PENDING_REVIEW"
    by_version = {v["version"]: v for v in head2["versions"]}
    assert by_version[1]["reviewStatus"] == "APPROVED"
    assert by_version[1]["content"] != edited
    assert by_version[2]["reviewStatus"] == "PENDING_REVIEW"


def test_review_state_endpoint():
    _, _, run = setup_matched_scenario()
    notice_id = get_head(run["draftId"])["noticeId"]
    state = client.get(f"/api/notices/{notice_id}/review").json()
    assert state["draftId"] == run["draftId"]
    assert state["currentVersion"] == 1
    assert state["reviewStatus"] == "PENDING_REVIEW"


def test_invalid_action_rejected():
    _, _, run = setup_matched_scenario()
    res = client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "AUTO_APPROVE", "comment": "x"}
    )
    assert res.status_code == 400


# ---------- audit ----------

def test_audit_trail_chronological_and_typed():
    notice, _, run = setup_matched_scenario()
    events = client.get(f"/api/notices/{notice['id']}/audit").json()
    actions = [e["action"] for e in events]
    for expected in ("DOCUMENT_UPLOADED", "RETURN_UPLOADED", "RECONCILIATION_COMPLETED",
                     "RECONCILIATION_REVIEWED", "DRAFT_GENERATED"):
        assert expected in actions, actions
    created = [e["createdAt"] for e in events]
    assert created == sorted(created)
    by_action = {e["action"]: e for e in events}
    assert by_action["DOCUMENT_UPLOADED"]["actorType"] == "SYSTEM"
    assert by_action["RECONCILIATION_REVIEWED"]["actorType"] == "AGENT"
    assert by_action["DRAFT_GENERATED"]["actorType"] == "AGENT"


def test_audit_records_review_actions_and_edits():
    notice, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    client.put(f"/api/drafts/{run['draftId']}", json={"content": head["content"] + "\nNote."})
    client.post(
        f"/api/drafts/{run['draftId']}/review",
        json={"action": "REQUEST_CHANGES", "comment": "Clarify residual."},
    )
    actions = [e["action"] for e in client.get(f"/api/notices/{notice['id']}/audit").json()]
    assert "DRAFT_EDITED" in actions
    assert "CHANGES_REQUESTED" in actions
    edited = next(e for e in client.get(f"/api/notices/{notice['id']}/audit").json()
                  if e["action"] == "DRAFT_EDITED")
    assert edited["actorType"] == "REVIEWER"
    assert edited["metadata"]["version"] == 2


def test_audit_events_never_overwritten():
    notice, _, run = setup_matched_scenario()
    before = client.get(f"/api/notices/{notice['id']}/audit").json()
    client.post(
        f"/api/drafts/{run['draftId']}/review", json={"action": "APPROVE", "comment": "ok"}
    )
    after = client.get(f"/api/notices/{notice['id']}/audit").json()
    before_ids = {e["id"] for e in before}
    assert before_ids <= {e["id"] for e in after}
    assert len(after) == len(before) + 1


def test_draft_scoped_audit():
    _, _, run = setup_matched_scenario()
    events = client.get(f"/api/drafts/{run['draftId']}/audit").json()
    assert any(e["action"] == "DRAFT_GENERATED" for e in events)


# ---------- validation ----------

def test_validator_accepts_agent_draft():
    notice, _, run = setup_matched_scenario()
    content = get_head(run["draftId"])["content"]
    ok, errors = validation.validate_draft(content, notice["id"])
    assert ok, errors


def test_validator_rejects_invented_figure():
    notice, _, run = setup_matched_scenario()
    content = get_head(run["draftId"])["content"]
    ok, errors = validation.validate_draft(content + "\nWe accept Rs. 99,99,999.00.", notice["id"])
    assert not ok and any("99" in e or "backend records" in e for e in errors)


def test_validator_rejects_bad_citations():
    notice, _, run = setup_matched_scenario()
    content = get_head(run["draftId"])["content"]
    ok, _ = validation.validate_draft(content + "\nSee [Finding invented-1].", notice["id"])
    assert not ok
    ok, _ = validation.validate_draft(content + "\nSee [Evidence ret_invented].", notice["id"])
    assert not ok
    ok, _ = validation.validate_draft(content + "\nPer [Rule 999 / 2026-09-30.v1].", notice["id"])
    assert not ok


def test_validator_rejects_banned_language_and_missing_review_line():
    notice, _, run = setup_matched_scenario()
    content = get_head(run["draftId"])["content"]
    ok, _ = validation.validate_draft(content + "\nThis is guaranteed acceptance.", notice["id"])
    assert not ok
    stripped = re.sub(r"(?i)review required before submission\.?", "", content)
    ok, errors = validation.validate_draft(stripped, notice["id"])
    assert not ok and any("Review-required" in e for e in errors)


def test_validator_rejects_wrong_gstin_and_period():
    notice, _, run = setup_matched_scenario()
    content = get_head(run["draftId"])["content"]
    ok, _ = validation.validate_draft(content + "\nGSTIN: 12FAKEA0000B1Z8", notice["id"])
    assert not ok
    tampered = content.replace("Tax period: 2025-07", "Tax period: 2024-04")
    ok, _ = validation.validate_draft(tampered, notice["id"])
    assert not ok


def test_put_rejects_invalid_citations_and_figures():
    _, _, run = setup_matched_scenario()
    head = get_head(run["draftId"])
    res = client.put(
        f"/api/drafts/{run['draftId']}",
        json={"content": head["content"] + "\nSee [Evidence ret_nope]."},
    )
    assert res.status_code == 422
    # Failed edit creates no version.
    assert get_head(run["draftId"])["currentVersion"] == 1


# ---------- PDF ----------

def test_pdf_export_content():
    _, _, run = setup_matched_scenario()
    res = client.get(f"/api/drafts/{run['draftId']}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert len(res.content) > 2000


def test_pdf_contains_provenance():
    _, _, run = setup_matched_scenario()
    res = client.get(f"/api/drafts/{run['draftId']}/pdf")
    text = _pdf_text(res.content)
    for needle in ("REVIEW DRAFT", "NOT FILED", "Review required before submission",
                   "48,260.00", "NoticePilot does not submit", "DRC-01B/2025-26/SYN/5005"):
        assert needle in text, needle


def _pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ImportError:
        # Fallback: raw bytes still contain literal strings for ASCII runs.
        return content.decode("latin-1", errors="ignore")


def test_pdf_unknown_version_404():
    _, _, run = setup_matched_scenario()
    assert client.get(f"/api/drafts/{run['draftId']}/pdf?version=99").status_code == 404


# ---------- integration ----------

def test_full_review_workflow():
    notice = make_notice()
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    client.post(f"/api/notices/{notice['id']}/reconciliation")
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    draft_id = run["draftId"]

    # v1 -> reviewer edits -> v2
    v1 = get_head(draft_id)["content"]
    r = client.put(f"/api/drafts/{draft_id}", json={"content": v1 + "\nReviewer note: verified."})
    assert r.json()["currentVersion"] == 2
    # request changes -> v2 edit -> v3
    client.post(f"/api/drafts/{draft_id}/review",
                json={"action": "REQUEST_CHANGES", "comment": "Tighten the position wording."})
    v2 = get_head(draft_id)["content"]
    r = client.put(f"/api/drafts/{draft_id}", json={"content": v2 + "\nPosition tightened."})
    assert r.json()["currentVersion"] == 3
    # approve v3
    r = client.post(f"/api/drafts/{draft_id}/review",
                    json={"action": "APPROVE", "comment": "Reviewed; ready as draft."})
    assert r.json()["status"] == "APPROVED"
    # audit shows every action in order
    actions = [e["action"] for e in client.get(f"/api/notices/{notice['id']}/audit").json()]
    for expected in ("DOCUMENT_UPLOADED", "RETURN_UPLOADED", "RECONCILIATION_COMPLETED",
                     "RECONCILIATION_REVIEWED", "DRAFT_GENERATED", "DRAFT_EDITED",
                     "CHANGES_REQUESTED", "APPROVED"):
        assert expected in actions, actions
    # PDF of approved v3
    pdf = client.get(f"/api/drafts/{draft_id}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    text = _pdf_text(pdf.content)
    assert "NOT FILED" in text and "does not submit" in text
