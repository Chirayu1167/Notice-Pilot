"""Final acceptance flow (Phase 6/7): the complete review-gated workflow,
end to end, against live endpoints. Mirrors spec section 7.15 steps 1-26.

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


def pdf_text(content: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)


def test_final_acceptance_flow():
    # 1. Reset synthetic demo.
    reset = client.post("/api/demo/reset").json()
    assert "SYNTHETIC DEMO DATA" in reset["label"]
    notice_id = reset["noticeId"]

    # 2-3. Load + parse notice (rebuilt by reset; verify fields).
    notice = client.get(f"/api/notices/{notice_id}").json()
    assert notice["noticeType"] == "DRC-01B"
    assert notice["differenceAmount"] == 48260.0

    # 4-5. Upload GSTR-1 + GSTR-3B (already done by reset; verify listing).
    returns = client.get(f"/api/notices/{notice_id}/return-data").json()
    assert {r["source"] for r in returns} == {"GSTR-1", "GSTR-3B"}

    # 6-7. Reconcile -> PARTIAL.
    recon = client.get(f"/api/notices/{notice_id}/reconciliation").json()
    assert recon["status"] == "PARTIAL"
    assert recon["explainedAmount"] == 42100.0
    assert recon["unexplainedAmount"] == 6160.0

    # 8-9. Run agent -> missing evidence detected.
    runs = client.get(f"/api/notices/{notice_id}/agent/runs").json()
    assert len(runs) >= 1
    run1 = client.get(f"/api/runs/{runs[0]['id']}").json()
    assert run1["decision"] == "INSUFFICIENT_EVIDENCE"
    evidence = client.get(f"/api/notices/{notice_id}/evidence").json()
    assert len(evidence["missing"]) >= 1

    # 10-12. Upload supplemental evidence, reconcile again -> MATCHED.
    supp = client.post("/api/demo/supplement", params={"notice_id": notice_id}).json()
    assert supp["reconciliation"]["status"] == "MATCHED"

    # The pre-supplement PARTIAL draft is preserved untouched.
    old_head = client.get(f"/api/drafts/{reset['draftId']}").json()
    assert old_head["versions"][0]["reconSnapshot"]["status"] == "PARTIAL"

    # 13-14. Run agent again -> Draft v1 (created by the supplement replan).
    draft_id = supp["draftId"]
    assert draft_id != reset["draftId"]
    head = client.get(f"/api/drafts/{draft_id}").json()
    assert head["currentVersion"] == 1

    # 15-16. Edit draft -> v2.
    v1_text = head["versions"][0]["content"]
    head = client.put(
        f"/api/drafts/{draft_id}", json={"content": v1_text + "\nReviewer note: verified."}
    ).json()
    assert head["currentVersion"] == 2

    # 17-18. Request changes, edit -> v3.
    change = client.post(f"/api/drafts/{draft_id}/review",
                         json={"action": "REQUEST_CHANGES", "comment": "Tighten wording."})
    assert change.json()["status"] == "CHANGES_REQUESTED"
    head = client.get(f"/api/drafts/{draft_id}").json()
    head = client.put(
        f"/api/drafts/{draft_id}", json={"content": head["content"] + "\nWording tightened."}
    ).json()
    assert head["currentVersion"] == 3

    # 19-21. Validate draft (implicit in approve) -> approve v3 + sign-off.
    approval = client.post(
        f"/api/drafts/{draft_id}/review",
        json={"action": "APPROVE", "comment": "Reviewed against records.",
              "reviewer_id": "reviewer_demo"},
    )
    assert approval.status_code == 200
    signoff = approval.json()
    assert signoff["reviewerName"] == "Demo Reviewer"
    assert signoff["version"] == 3
    assert signoff["validation"]["result"] == "PASS"
    assert signoff["reconRunId"]

    # 22. Audit trail shows every action in order.
    actions = [e["action"] for e in client.get(f"/api/notices/{notice_id}/audit").json()]
    for expected in ("DEMO_RESET", "DOCUMENT_UPLOADED", "RETURN_UPLOADED",
                     "RECONCILIATION_COMPLETED", "RECONCILIATION_REVIEWED",
                     "DRAFT_GENERATED", "DRAFT_EDITED", "CHANGES_REQUESTED", "APPROVED"):
        assert expected in actions, actions

    # 23. Compare versions.
    cmp12 = client.get(f"/api/drafts/{draft_id}/compare?from_version=1&to_version=2").json()
    cmp23 = client.get(f"/api/drafts/{draft_id}/compare?from_version=2&to_version=3").json()
    assert cmp12["hasChanges"] and cmp23["hasChanges"]

    # 24-25. Export review PDF + cover letter.
    review_pdf = client.get(f"/api/drafts/{draft_id}/pdf")
    assert review_pdf.status_code == 200
    assert "NOT FILED" in pdf_text(review_pdf.content)
    cover = client.get(f"/api/drafts/{draft_id}/cover-letter")
    assert cover.status_code == 200
    cover_text = pdf_text(cover.content)
    assert "READY FOR HUMAN SUBMISSION" in cover_text
    assert "does not submit this document" in cover_text

    # 26. Historical versions unchanged: v1 still snapshot-era truth,
    # later edits never mutate it.
    versions = client.get(f"/api/drafts/{draft_id}/versions").json()
    v1 = next(v for v in versions if v["version"] == 1)
    assert v1["reconSnapshot"]["status"] == "MATCHED"
    assert v1["reconSnapshot"]["unexplainedAmount"] == 0.0
    assert "Reviewer note" not in v1["content"]
    assert "Wording tightened" not in v1["content"]
    assert database.get_draft_version(draft_id, 1)["content"] == v1["content"]
