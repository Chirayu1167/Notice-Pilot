"""Synthetic demo workspace (Phase 6). Deterministic reset/replay of the
documented demo scenario. Operates ONLY on rows identified by synthetic demo
fixture markers — never on arbitrary user data — and only on files inside the
application storage directories."""

import os
import uuid

from app import database
from app.services import storage

DEMO_LABEL = "SYNTHETIC DEMO DATA \u2014 NOT A REAL GST CASE"

DEMO_NOTICE_NUMBERS = ["DRC-01B/2025-26/SYN/5005"]
DEMO_DOCUMENT_FILENAMES = ["synthetic_drc01b_48260.txt"]

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "tests", "fixtures",
)
RETURNS_DIR = os.path.join(FIXTURE_DIR, "returns")

NOTICE_FIXTURE = "synthetic_drc01b_48260.txt"
INITIAL_RETURNS = [
    ("agent_gstr1_initial_2025-07.csv", "GSTR-1", "2025-07"),
    ("agent_gstr3b_2025-07.csv", "GSTR-3B", "2025-07"),
]
SUPPLEMENTAL_RETURN = ("agent_gstr1_supplemental_2025-07.csv", "GSTR-1", "2025-07")


def demo_enabled() -> bool:
    return (os.environ.get("DEMO_ENABLED") or "1").strip() != "0"


def _fixture_bytes(*parts: str) -> bytes:
    path = os.path.realpath(os.path.join(FIXTURE_DIR, *parts))
    base = os.path.realpath(FIXTURE_DIR)
    if path != base and not path.startswith(base + os.sep):
        raise ValueError("Fixture path escapes fixtures directory.")
    with open(path, "rb") as f:
        return f.read()


def _unlink_workspace_files(files: list[tuple[str, str, str]]) -> int:
    removed = 0
    for base_dir, owner_id, filename in files:
        try:
            if base_dir == storage.config.DOCUMENTS_DIR:
                path = storage.contained_path(base_dir, storage.get_document_path(owner_id, filename))
            else:
                path = storage.contained_path(base_dir, storage.get_return_file_path(owner_id, filename))
        except ValueError:
            continue
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            continue
    return removed


def clear_demo_workspace() -> dict:
    rows = database.find_demo_notices(DEMO_NOTICE_NUMBERS, DEMO_DOCUMENT_FILENAMES)
    cleared, files_removed = 0, 0
    for row in rows:
        info = database.delete_notice_workspace(row["id"])
        files_removed += _unlink_workspace_files(info["files"])
        cleared += 1
    return {"clearedNotices": cleared, "removedFiles": files_removed}


def _upload_notice() -> tuple[str, str]:
    from app.services import notice_service

    content = _fixture_bytes(NOTICE_FIXTURE)
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    storage.save_document(doc_id, NOTICE_FIXTURE, content)
    database.create_document(doc_id, NOTICE_FIXTURE, "text/plain", len(content))
    notice = notice_service.parse_document(doc_id)
    database.create_audit_event(
        notice["id"], "SYSTEM", "", "DOCUMENT_UPLOADED", "document", doc_id,
        {"filename": NOTICE_FIXTURE, "demo": True},
    )
    return notice["id"], doc_id


def _upload_return(notice_id: str, filename: str, source: str, period: str) -> dict:
    from app.services import return_service

    content = _fixture_bytes("returns", filename)
    result = return_service.upload_return_data(notice_id, filename, content, source, period)
    database.create_audit_event(
        notice_id, "SYSTEM", "", "RETURN_UPLOADED", "return_document", result["id"],
        {"source": source, "filename": filename, "demo": True},
    )
    return result


def reset_demo() -> dict:
    """Clear demo workspaces and rebuild the initial mismatch state."""
    from app.agent import orchestrator
    from app.services import reconciliation as recon_service

    cleared = clear_demo_workspace()
    notice_id, _ = _upload_notice()
    for filename, source, period in INITIAL_RETURNS:
        _upload_return(notice_id, filename, source, period)
    recon = recon_service.run_reconciliation(notice_id)
    database.create_audit_event(
        notice_id, "SYSTEM", "", "RECONCILIATION_COMPLETED", "reconciliation_run",
        recon["id"], {"status": recon.get("status"), "demo": True},
    )
    run = orchestrator.run_agent(notice_id)
    database.create_audit_event(
        notice_id, "SYSTEM", "", "DEMO_RESET", "notice", notice_id,
        {"label": DEMO_LABEL, "stage": "initial-mismatch"},
    )
    return {
        "label": DEMO_LABEL,
        "noticeId": notice_id,
        "stage": "initial-mismatch",
        "reconciliation": {
            "status": recon["status"],
            "noticeDifference": recon["noticeDifference"],
            "explainedAmount": recon["explainedAmount"],
            "unexplainedAmount": recon["unexplainedAmount"],
        },
        "agentRun": {"id": run["id"], "status": run["status"], "decision": run["decision"]},
        "draftId": run.get("draftId"),
        **cleared,
    }


def supplement_demo(notice_id: str) -> dict:
    """Upload the supplemental demo return and replan (recon + agent)."""
    from app.agent import orchestrator
    from app.services import reconciliation as recon_service

    notice = database.get_notice(notice_id)
    if notice is None:
        raise KeyError(notice_id)
    if notice["notice_number"] not in DEMO_NOTICE_NUMBERS:
        raise ValueError("Supplemental demo evidence applies to the demo notice only.")
    filename, source, period = SUPPLEMENTAL_RETURN
    uploaded = _upload_return(notice_id, filename, source, period)
    recon = recon_service.run_reconciliation(notice_id)
    database.create_audit_event(
        notice_id, "SYSTEM", "", "RECONCILIATION_COMPLETED", "reconciliation_run",
        recon["id"], {"status": recon.get("status"), "demo": True},
    )
    run = orchestrator.run_agent(notice_id)
    return {
        "label": DEMO_LABEL,
        "noticeId": notice_id,
        "stage": "reconciled",
        "uploadedReturnId": uploaded["id"],
        "reconciliation": {
            "status": recon["status"],
            "noticeDifference": recon["noticeDifference"],
            "explainedAmount": recon["explainedAmount"],
            "unexplainedAmount": recon["unexplainedAmount"],
        },
        "agentRun": {"id": run["id"], "status": run["status"], "decision": run["decision"]},
        "draftId": run.get("draftId"),
    }
