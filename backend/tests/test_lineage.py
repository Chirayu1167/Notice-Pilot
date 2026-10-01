"""Evidence lineage tests: NOTICE -> FINDING -> CALCULATION -> RETURN ROW
-> SOURCE DOCUMENT -> ORIGINAL FILE."""

import os
import sqlite3

from fastapi.testclient import TestClient

from app import database
from app.main import app
from tests.conftest import fixture_path

client = TestClient(app)

RETURNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "returns")


def return_bytes(name: str) -> bytes:
    with open(os.path.join(RETURNS, name), "rb") as f:
        return f.read()


def make_notice(fixture_name: str) -> dict:
    with open(fixture_path(fixture_name), "rb") as f:
        doc_id = client.post(
            "/api/documents/upload", files={"file": (fixture_name, f.read())}
        ).json()["document"]["id"]
    return client.post(f"/api/notices/parse/{doc_id}").json()


def upload_return(notice_id: str, name: str):
    return client.post(
        f"/api/notices/{notice_id}/return-data",
        files={"file": (name, return_bytes(name))},
    )


def setup_matched_01b():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    run = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert run["status"] == "MATCHED"
    return notice, run


def test_every_finding_has_calculation():
    _, run = setup_matched_01b()
    assert run["findings"]
    for f in run["findings"]:
        calc = f.get("calculation")
        assert calc, f"finding {f['id']} has no calculation"
        assert calc.get("rule"), f"finding {f['id']} has no rule"
        assert calc.get("formula"), f"finding {f['id']} has no formula"
        assert isinstance(calc.get("inputs"), dict)
        assert calc.get("ruleVersion")


def test_lineage_full_chain():
    _, run = setup_matched_01b()
    target = next(f for f in run["findings"] if f["category"] == "MATCHED_COMPONENT")
    lineage = client.get(f"/api/reconciliation/findings/{target['id']}/lineage")
    assert lineage.status_code == 200, lineage.text
    body = lineage.json()

    assert body["chain"] == ["NOTICE", "FINDING", "CALCULATION", "RETURN_ROW", "SOURCE_DOCUMENT", "ORIGINAL_FILE"]

    # NOTICE
    assert body["notice"]["id"] == run["noticeId"]
    assert body["notice"]["noticeType"] == "DRC-01B"
    # FINDING
    assert body["finding"]["id"] == target["id"]
    # CALCULATION
    assert body["calculation"]["rule"] == "CGST Rule 88C"
    assert "GSTR-1" in body["calculation"]["formula"]
    assert body["calculation"]["inputs"]["gstr1Total"] == 54000.0
    assert body["calculation"]["inputs"]["gstr3bTotal"] == 45000.0
    assert body["calculation"]["inputs"]["calculatedDifference"] == 9000.0
    # RETURN ROW
    assert len(body["returnRows"]) == len(target["sourceRows"])
    row = body["returnRows"][0]
    for field in ("id", "returnId", "source", "invoiceNumber", "totalTax", "raw"):
        assert field in row, f"row missing {field}"
    assert all(r["returnId"] for r in body["returnRows"])
    # SOURCE DOCUMENT -> ORIGINAL FILE
    assert body["returnDocuments"], "expected source documents"
    sources = {d["source"] for d in body["returnDocuments"]}
    assert sources == {"GSTR-1", "GSTR-3B"}
    for doc in body["returnDocuments"]:
        assert doc["originalFileStored"] is True
        assert doc["downloadUrl"].endswith("/download")
    # Notice source document
    assert body["noticeDocument"]["downloadUrl"].startswith("/api/documents/")


def test_lineage_rows_match_finding_source_rows():
    _, run = setup_matched_01b()
    for f in run["findings"]:
        if not f["sourceRows"]:
            continue
        body = client.get(f"/api/reconciliation/findings/{f['id']}/lineage").json()
        assert [r["id"] for r in body["returnRows"]] == sorted(f["sourceRows"])


def test_lineage_01c_rule():
    notice = make_notice("synthetic_drc01c_apr2024.txt")
    upload_return(notice["id"], "gstr2b_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_itc_2024-04.csv")
    run = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    target = next(f for f in run["findings"] if f["category"] == "MATCHED_COMPONENT")
    body = client.get(f"/api/reconciliation/findings/{target['id']}/lineage").json()
    assert body["calculation"]["rule"] == "CGST Rule 88D"
    assert body["calculation"]["inputs"]["calculatedDifference"] == 5000.0


def test_download_original_file_bytes_identical():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    original = return_bytes("gstr1_matched_2024-04.csv")
    meta = upload_return(notice["id"], "gstr1_matched_2024-04.csv").json()
    res = client.get(f"/api/notices/{notice['id']}/return-data/{meta['id']}/download")
    assert res.status_code == 200
    assert res.content == original


def test_download_missing_file_honest_404(tmp_path):
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    meta = upload_return(notice["id"], "gstr1_matched_2024-04.csv").json()
    # Simulate a legacy upload whose bytes were never stored.
    from app.services import storage as storage_mod

    path = storage_mod.get_return_file_path(meta["id"], meta["filename"])
    os.remove(path)
    try:
        res = client.get(f"/api/notices/{notice['id']}/return-data/{meta['id']}/download")
        assert res.status_code == 404
        assert "Re-upload" in res.json()["detail"]
    finally:
        with open(path, "wb") as f:
            f.write(return_bytes("gstr1_matched_2024-04.csv"))


def test_return_rows_endpoint():
    notice, run = setup_matched_01b()
    target = next(f for f in run["findings"] if f["category"] == "GSTR1_TOTAL")
    ids = ",".join(target["sourceRows"])
    rows = client.get(f"/api/notices/{notice['id']}/return-rows?ids={ids}").json()
    assert len(rows) == 3
    assert {r["source"] for r in rows} == {"GSTR-1"}
    assert rows[0]["raw"].get("Remarks", "").startswith("SYNTHETIC DEMO DATA")


def test_return_rows_requires_ids():
    notice, _ = setup_matched_01b()
    assert client.get(f"/api/notices/{notice['id']}/return-rows").status_code == 400


def test_return_rows_cross_notice_isolation():
    notice_a, run_a = setup_matched_01b()
    notice_b = make_notice("synthetic_drc01c_apr2024.txt")
    target = next(f for f in run_a["findings"] if f["category"] == "GSTR1_TOTAL")
    ids = ",".join(target["sourceRows"])
    rows = client.get(f"/api/notices/{notice_b['id']}/return-rows?ids={ids}").json()
    assert rows == []


def test_lineage_unknown_finding_404():
    assert client.get("/api/reconciliation/findings/finding_nope/lineage").status_code == 404


def test_lineage_deterministic():
    _, run = setup_matched_01b()
    target = run["findings"][0]
    first = client.get(f"/api/reconciliation/findings/{target['id']}/lineage").json()
    second = client.get(f"/api/reconciliation/findings/{target['id']}/lineage").json()
    assert first == second


def test_migrate_findings_adds_columns_to_legacy_table():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE findings (id TEXT PRIMARY KEY, run_id TEXT, notice_id TEXT, "
        "category TEXT, description TEXT, amount REAL, source_rows_json TEXT, status TEXT)"
    )
    database._migrate_findings(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(findings)").fetchall()}
    assert {"rule", "formula", "inputs_json"} <= cols
    # Idempotent on second run.
    database._migrate_findings(conn)
    conn.close()
