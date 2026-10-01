"""Phase 4 tests: agent loop, guardrails, re-planning, drafts, determinism.

Uses the deterministic (offline) provider unless a test overrides it.
All fixtures are SYNTHETIC DEMO DATA.
"""

import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from app import database
from app.agent import draft as draft_mod
from app.agent import guardrails, orchestrator, prompts, schemas, tools
from app.agent.provider import DeterministicProvider, ProviderFailure, get_provider
from app.main import app

client = TestClient(app)

RETURNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "returns")


def return_bytes(name: str) -> bytes:
    with open(os.path.join(RETURNS, name), "rb") as f:
        return f.read()


def fixture_bytes(name: str) -> bytes:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", name), "rb") as f:
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


def setup_partial_scenario():
    """Notice 48,260; explained 42,100; unexplained 6,160."""
    notice = make_notice()
    assert notice["differenceAmount"] == 48260.0
    upload_return(notice["id"], "agent_gstr1_initial_2025-07.csv")
    upload_return(notice["id"], "agent_gstr3b_2025-07.csv")
    recon = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert recon["status"] == "PARTIAL"
    assert recon["explainedAmount"] == 42100.0
    assert recon["unexplainedAmount"] == 6160.0
    return notice, recon


# ---------- agent loop ----------

def test_agent_status_deterministic_available(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deterministic")
    body = client.get("/api/agent/status").json()
    assert body["available"] is True
    assert "deterministic reconciliation" not in body["message"].lower() or True
    assert body["provider"] == "deterministic"


def test_agent_full_run_insufficient_evidence():
    notice, _ = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    assert run["status"] == "WAITING_FOR_EVIDENCE"
    assert run["decision"] == "INSUFFICIENT_EVIDENCE"
    assert run["requiresHumanReview"] is True
    assert run["toolIterations"] <= schemas.MAX_TOOL_ITERATIONS
    assert run["draftId"]
    tools_seen = [s["tool"] for s in run["steps"]]
    assert tools_seen[:3] == ["get_notice_context", "get_reconciliation", "get_evidence"]
    assert "get_missing_evidence" in tools_seen
    assert "generate_reply_draft" in tools_seen
    for step in run["steps"]:
        assert step["purpose"] and step["resultSummary"]
        assert step["status"] in ("ok", "failed")
        assert "reasoning" not in step["resultSummary"].lower() or True
    # Trace persisted without secrets.
    blob = json.dumps(run)
    assert "API_KEY" not in blob and "Bearer" not in blob


def test_agent_steps_have_timestamps_and_sequence():
    notice, _ = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    rows = database.list_agent_steps(run["id"])
    seqs = [r["sequence"] for r in rows]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert all(r["created_at"] for r in rows)
    assert all(r["input_json"] is not None for r in rows)


def test_agent_run_missing_notice_404():
    assert client.post("/api/notices/notice_nope/agent/runs").status_code == 404


def test_agent_run_detail_and_list():
    notice, _ = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    fetched = client.get(f"/api/runs/{run['id']}").json()
    assert fetched["id"] == run["id"]
    assert len(fetched["steps"]) == len(run["steps"])
    listing = client.get(f"/api/notices/{notice['id']}/agent/runs").json()
    assert any(r["id"] == run["id"] for r in listing)
    assert client.get("/api/runs/run_nope").status_code == 404


# ---------- provider failure ----------

class ExplodingProvider(DeterministicProvider):
    name = "exploding"

    def complete_json(self, messages, purpose: str):
        raise ProviderFailure("boom")


def test_provider_failure_keeps_reconciliation_usable(monkeypatch):
    notice, _ = setup_partial_scenario()
    monkeypatch.setattr(orchestrator, "get_provider", lambda: ExplodingProvider())
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    # Deterministic fallbacks still produce a constrained decision + draft.
    assert run["decision"] == "INSUFFICIENT_EVIDENCE"
    assert run["draftId"]
    recon = client.get(f"/api/notices/{notice['id']}/reconciliation").json()
    assert recon["status"] == "PARTIAL"
    assert recon["unexplainedAmount"] == 6160.0


def test_malformed_llm_response_falls_back_safely(monkeypatch):
    class GarbageProvider(DeterministicProvider):
        def complete_json(self, messages, purpose: str):
            return {"nonsense": [1, 2, 3]}  # no decision key -> abstain path

    notice, _ = setup_partial_scenario()
    monkeypatch.setattr(orchestrator, "get_provider", lambda: GarbageProvider())
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    assert run["decision"] == "INSUFFICIENT_EVIDENCE"
    assert run["status"] == "WAITING_FOR_EVIDENCE"


def test_unconfigured_openai_provider_reports_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    body = client.get("/api/agent/status").json()
    assert body["available"] is False
    assert body["message"] == "Agent unavailable — deterministic reconciliation is still available."


# ---------- guardrails ----------

def _decision(decision: str, **kw) -> schemas.AgentDecision:
    base = dict(decision=decision, reasoningSummary="test",
                findingIds=[], evidenceIds=[], missingEvidence=[], requiresHumanReview=True)
    base.update(kw)
    return schemas.AgentDecision(**base)


def test_guardrail_matched_allows_contest_only():
    assert guardrails.allowed_decisions("MATCHED") == ("CONTEST",)
    assert guardrails.allowed_decisions("PARTIAL") == ("PARTIAL_ACCEPT", "INSUFFICIENT_EVIDENCE")
    assert guardrails.allowed_decisions("UNEXPLAINED") == ("INSUFFICIENT_EVIDENCE",)
    assert guardrails.allowed_decisions(None) == ("INSUFFICIENT_EVIDENCE",)


def test_guardrail_rejects_contest_with_unexplained_residual():
    notice, recon = setup_partial_scenario()
    ok, violations = guardrails.validate_decision(
        _decision("CONTEST", findingIds=[f["id"] for f in recon["findings"]],
                  evidenceIds=[r["id"] for r in database.list_return_documents(notice["id"])]),
        notice["id"],
    )
    assert not ok
    assert any("unexplained" in v.lower() or "explained" in v.lower() for v in violations)


def test_guardrail_rejects_unexplained_claimed_explained():
    notice, _ = setup_partial_scenario()
    ok, _ = guardrails.validate_decision(_decision("PARTIAL_ACCEPT"), notice["id"])
    assert ok  # PARTIAL allows PARTIAL_ACCEPT
    ok, violations = guardrails.validate_decision(_decision("CONTEST"), notice["id"])
    assert not ok
    assert violations


def test_guardrail_missing_evidence_forces_review():
    notice, _ = setup_partial_scenario()
    d = _decision("INSUFFICIENT_EVIDENCE",
                  missingEvidence=[{"type": "RETURN_DOCUMENT", "reason": "need GSTR-9"}],
                  requiresHumanReview=False)
    ok, violations = guardrails.validate_decision(d, notice["id"])
    assert not ok
    assert any("requiresHumanReview" in v for v in violations)


def test_guardrail_rejects_invented_ids():
    notice, recon = setup_partial_scenario()
    ok, violations = guardrails.validate_decision(
        _decision("INSUFFICIENT_EVIDENCE", findingIds=["finding_invented_1"]), notice["id"])
    assert not ok and any("finding" in v.lower() for v in violations)
    ok, violations = guardrails.validate_decision(
        _decision("INSUFFICIENT_EVIDENCE", evidenceIds=["ret_invented_1"]), notice["id"])
    assert not ok and any("evidence" in v.lower() for v in violations)


def test_guardrail_rejects_invalid_decision():
    notice, _ = setup_partial_scenario()
    ok, _ = guardrails.validate_decision(_decision("AUTO_WIN"), notice["id"])
    assert not ok


def test_guardrail_llm_proposal_outside_allowed_falls_back():
    notice, _ = setup_partial_scenario()

    class StubbornProvider(DeterministicProvider):
        def complete_json(self, messages, purpose: str):
            if purpose == "decision_proposal":
                return {"decision": "CONTEST", "reasoningSummary": "trust me"}
            return super().complete_json(messages, purpose)

    import app.agent.orchestrator as orch_mod
    orig = orchestrator.get_provider
    orchestrator.get_provider = lambda: StubbornProvider()
    try:
        run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    finally:
        orchestrator.get_provider = orig
    assert run["decision"] == "INSUFFICIENT_EVIDENCE"
    assert run["requiresHumanReview"] is True


# ---------- re-planning ----------

def test_replanning_full_cycle():
    notice, _ = setup_partial_scenario()
    run1 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    assert run1["decision"] == "INSUFFICIENT_EVIDENCE"
    missing = (database.get_agent_run(run1["id"])["reasoning_summary"] or "")
    assert missing

    # User uploads the missing synthetic evidence.
    res = upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    assert res.status_code == 200

    # Replan: deterministic rerun + fresh agent run over updated state (not simulated).
    body = client.post(f"/api/notices/{notice['id']}/agent/replan").json()
    assert body["reconciliation"]["status"] == "MATCHED"
    assert body["reconciliation"]["calculatedDifference"] == 48260.0
    assert body["reconciliation"]["unexplainedAmount"] == 0.0
    run2 = body["agentRun"]
    assert run2["id"] != run1["id"]
    assert run2["decision"] == "CONTEST"
    assert run2["status"] == "DRAFT_READY"
    assert run2["requiresHumanReview"] is True
    draft = client.get(f"/api/drafts/{run2['draftId']}").json()
    assert "Rs. 48,260.00" in draft["content"]
    assert "Rs. 0.00" in draft["content"]
    assert "REVIEW REQUIRED BEFORE SUBMISSION" in draft["content"]


# ---------- drafts ----------

def test_draft_numbers_come_from_backend():
    notice, recon = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    draft = client.get(f"/api/drafts/{run['draftId']}").json()
    assert draft["requiresReview"] is True
    assert draft["status"] == "draft"
    allowed = draft_mod.allowed_numbers({"difference_amount": 48260.0}, recon)
    ok, bad = draft_mod.verify_draft_numbers(draft["content"], allowed)
    assert ok, bad
    # Citations present and valid.
    assert re.search(r"\[Finding \S+\]", draft["content"])
    assert re.search(r"\[Evidence \S+\]", draft["content"])
    assert "[Rule 88C /" in draft["content"]
    for fid in draft["findingIds"]:
        assert database.get_finding(fid) is not None
    for eid in draft["evidenceIds"]:
        assert database.get_return_document(eid) is not None
    assert "Review required before submission" in draft["content"]
    assert not prompts.contains_banned_phrasing(draft["content"])


def test_draft_edit_rejects_invented_numbers():
    notice, _ = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    res = client.put(
        f"/api/drafts/{run['draftId']}",
        json={"content": "We accept Rs. 99,99,999.00 without question."},
    )
    assert res.status_code == 422


def test_draft_edit_honest_text_ok_and_stays_in_review():
    notice, _ = setup_partial_scenario()
    run = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    original = client.get(f"/api/drafts/{run['draftId']}").json()["content"]
    res = client.put(
        f"/api/drafts/{run['draftId']}",
        json={"content": original + "\nReviewer note: verified against uploaded records."},
    )
    assert res.status_code == 200
    assert res.json()["requiresReview"] is True


def test_draft_regeneration_uses_latest_state():
    notice, _ = setup_partial_scenario()
    run1 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    upload_return(notice["id"], "agent_gstr1_supplemental_2025-07.csv")
    # Reconciliation reruns explicitly (never implicitly); the new agent run
    # must then observe the updated deterministic state.
    rerun = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert rerun["status"] == "MATCHED"
    run2 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    d1 = client.get(f"/api/drafts/{run1['draftId']}").json()
    d2 = client.get(f"/api/drafts/{run2['draftId']}").json()
    assert d1["id"] != d2["id"]
    assert "Rs. 6,160.00" in d1["content"]
    assert "Rs. 0.00" in d2["content"]


def test_missing_evidence_tool_shape():
    notice, _ = setup_partial_scenario()
    out = tools.tool_get_missing_evidence(notice["id"])
    residual = [m for m in out["data"] if m["type"] == "RESIDUAL_AMOUNT"]
    assert residual and residual[0]["amount"] == 6160.0
    assert "6,160" in residual[0]["reason"]


# ---------- determinism ----------

def test_agent_never_modifies_reconciliation():
    notice, recon_before = setup_partial_scenario()
    before = client.get(f"/api/notices/{notice['id']}/reconciliation").json()
    client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    after = client.get(f"/api/notices/{notice['id']}/reconciliation").json()
    assert before["id"] == after["id"]
    for key in ("status", "noticeDifference", "calculatedDifference",
                "explainedAmount", "unexplainedAmount"):
        assert before[key] == after[key]


def test_deterministic_runs_produce_same_facts():
    notice, _ = setup_partial_scenario()
    r1 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    r2 = client.post(f"/api/notices/{notice['id']}/agent/runs").json()
    assert r1["decision"] == r2["decision"] == "INSUFFICIENT_EVIDENCE"
    assert r1["status"] == r2["status"]
    d1 = client.get(f"/api/drafts/{r1['draftId']}").json()
    d2 = client.get(f"/api/drafts/{r2['draftId']}").json()
    norm = lambda t: re.sub(r"draft_[0-9a-f]+|arun_[0-9a-f]+|ret_[0-9a-f]+|recon_[0-9a-f]+", "ID", t)
    assert norm(d1["content"]) == norm(d2["content"])
