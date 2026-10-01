"""Phase 2 tests: return upload, detection, normalization, validation, reconciliation."""

import io
import os

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.parsers import normalize as n
from app.parsers.return_parser import ReturnFileError, detect_source, parse_return_file
from tests.conftest import fixture_path

client = TestClient(app)

RETURNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "returns")


def return_path(name: str) -> str:
    return os.path.join(RETURNS, name)


def read_fixture(name: str) -> bytes:
    with open(return_path(name), "rb") as f:
        return f.read()


def make_notice(fixture_name: str) -> dict:
    with open(fixture_path(fixture_name), "rb") as f:
        doc_id = client.post(
            "/api/documents/upload", files={"file": (fixture_name, f.read())}
        ).json()["document"]["id"]
    notice = client.post(f"/api/notices/parse/{doc_id}").json()
    return notice


def upload_return(notice_id: str, name: str, **form):
    with open(return_path(name), "rb") as f:
        content = f.read()
    files = {"file": (name, content)}
    return client.post(f"/api/notices/{notice_id}/return-data", files=files, data=form)


# ---------- upload ----------

def test_upload_csv_gstr1():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "GSTR-1"
    assert body["period"] == "2024-04"
    assert body["rowCount"] == 3
    assert body["status"] == "READY"
    assert body["periodStatus"] == "MATCH"


def test_upload_xlsx_gstr1():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "gstr1_matched_2024-04.xlsx")
    assert res.status_code == 200, res.text
    assert res.json()["source"] == "GSTR-1"


def test_upload_xlsx_gstr3b():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "gstr3b_matched_2024-04.xlsx")
    assert res.status_code == 200, res.text
    assert res.json()["source"] == "GSTR-3B"


def test_upload_unsupported_extension():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = client.post(
        f"/api/notices/{notice['id']}/return-data",
        files={"file": ("notes.txt", b"hello")},
    )
    assert res.status_code == 422
    assert "CSV and XLSX" in res.json()["detail"]["message"]


def test_upload_malformed_xlsx():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = client.post(
        f"/api/notices/{notice['id']}/return-data",
        files={"file": ("fake.xlsx", b"not a zip file at all")},
    )
    assert res.status_code == 422


def test_upload_empty_file():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "empty_returns.csv")
    assert res.status_code == 422


def test_upload_unknown_source_rejected_with_guidance():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "arbitrary_expenses.csv")
    assert res.status_code == 422
    assert "select the return type" in res.json()["detail"]["message"].lower()


def test_upload_unknown_source_with_explicit_hint_accepted():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    # Ambiguous-but-valid summary file: detection is UNKNOWN, explicit user
    # identification (the documented flow) lets it parse as GSTR-3B.
    res = upload_return(notice["id"], "minimal_summary_2024-04.csv")
    assert res.status_code == 422
    res = upload_return(notice["id"], "minimal_summary_2024-04.csv", source="GSTR-3B")
    assert res.status_code == 200, res.text
    assert res.json()["source"] == "GSTR-3B"


def test_upload_missing_notice_404():
    res = client.post(
        "/api/notices/notice_nope/return-data",
        files={"file": ("gstr1_matched_2024-04.csv", read_fixture("gstr1_matched_2024-04.csv"))},
    )
    assert res.status_code == 404


def test_list_return_data():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    listing = client.get(f"/api/notices/{notice['id']}/return-data").json()
    assert {r["source"] for r in listing} == {"GSTR-1", "GSTR-3B"}


def test_document_scoped_upload_alias():
    with open(fixture_path("synthetic_drc01b_apr2024.txt"), "rb") as f:
        doc_id = client.post(
            "/api/documents/upload", files={"file": ("synthetic_drc01b_apr2024.txt", f.read())}
        ).json()["document"]["id"]
    notice = client.post(f"/api/notices/parse/{doc_id}").json()
    with open(return_path("gstr1_matched_2024-04.csv"), "rb") as f:
        res = client.post(
            f"/api/documents/{doc_id}/return-data",
            files={"file": ("gstr1_matched_2024-04.csv", f.read())},
        )
    assert res.status_code == 200, res.text
    assert res.json()["noticeId"] == notice["id"]


# ---------- detection ----------

def test_detect_gstr1():
    src, _ = detect_source(
        ["GSTIN/UIN of Recipient", "Invoice Number", "Invoice date", "Taxable Value", "IGST"],
        ["B2B Invoices"], "gstr1.csv",
    )
    assert src == "GSTR-1"


def test_detect_gstr3b():
    src, _ = detect_source(
        ["Nature of supplies", "Total Taxable Value", "IGST", "CGST", "SGST", "Cess"],
        ["Table 3.1"], "gstr3b.csv",
    )
    assert src == "GSTR-3B"


def test_detect_gstr2b():
    src, _ = detect_source(
        ["Supplier GSTIN", "Invoice Number", "ITC Available", "Bill of Entry"],
        ["GSTR-2B ITC"], "gstr2b.csv",
    )
    assert src == "GSTR-2B"


def test_detect_unknown_for_arbitrary_csv():
    src, _ = detect_source(["Date", "Category", "Spent", "Notes"], ["sheet1"], "expenses.csv")
    assert src == "UNKNOWN"


# ---------- normalization ----------

def test_normalize_numbers_dates_gstin():
    parsed = parse_return_file("gstr1_formats_2024-04.csv", read_fixture("gstr1_formats_2024-04.csv"))
    assert parsed["source"] == "GSTR-1"
    rows = parsed["rows"]
    assert len(rows) == 2
    r1, r2 = rows
    assert r1["taxable_value"] == 100000.0
    assert r1["igst"] == 18000.0
    assert r1["total_tax"] == 18000.0
    assert r1["invoice_date"] == "2024-04-05"
    assert r1["recipient_gstin"] == "27SYNTH0001A1Z5"
    assert r2["invoice_number"] == "INV-102"
    assert r2["cgst"] == 4500.0 and r2["sgst"] == 4500.0
    assert r2["total_tax"] == 9000.0
    assert all("raw" in r for r in rows)


def test_normalize_helpers_edge_cases():
    assert n.parse_number("₹1,00,000.00") == 100000.0
    assert n.parse_number("") is None
    assert n.parse_number("NaN") is None
    assert n.parse_number("-") is None
    assert n.parse_number("(1,000)") == -1000.0
    assert n.parse_date("05/04/2024") == "2024-04-05"
    assert n.parse_date("2024-04-05") == "2024-04-05"
    assert n.parse_date("") is None
    assert n.parse_gstin("27SYNTH0001A1Z5") == "27SYNTH0001A1Z5"
    assert n.parse_gstin("bogus") is None
    assert n.normalize_period("2024-04") == "2024-04"
    assert n.normalize_period("04/2024") == "2024-04"
    assert n.normalize_period("Apr-2024") == "2024-04"
    assert n.normalize_period("FY 2024-25") is None


def test_period_validation():
    assert n.compare_period("2024-04", "2024-04") == "MATCH"
    assert n.compare_period("2024-04", "2024-05") == "MISMATCH"
    assert n.compare_period("2024-25", "2024-04") == "UNKNOWN"
    assert n.compare_period(None, "2024-04") == "UNKNOWN"


def test_period_mismatch_flagged_on_upload():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = upload_return(notice["id"], "gstr1_may_2024-05.csv")
    assert res.status_code == 200, res.text
    assert res.json()["periodStatus"] == "MISMATCH"


# ---------- reconciliation ----------

def test_drc01b_matched():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    assert notice["differenceAmount"] == 9000.0
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    res = client.post(f"/api/notices/{notice['id']}/reconciliation")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "MATCHED"
    assert body["noticeDifference"] == 9000.0
    assert body["calculatedDifference"] == 9000.0
    assert body["explainedAmount"] == 9000.0
    assert body["unexplainedAmount"] == 0.0
    cats = {f["category"] for f in body["findings"]}
    assert {"GSTR1_TOTAL", "GSTR3B_TOTAL", "MATCHED_COMPONENT"} <= cats


def test_drc01b_partial_unexplained():
    # Same returns (calculated 9000) against the FY notice (difference 150000)
    notice = make_notice("synthetic_drc01b.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv", period="2024-04")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv", period="2024-04")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert body["status"] == "PARTIAL"
    assert body["calculatedDifference"] == 9000.0
    assert body["unexplainedAmount"] == pytest.approx(150000.0 - 9000.0)


def test_drc01b_missing_return():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert body["status"] == "MISSING_DATA"
    assert any(
        f["category"] == "MISSING_DATA" and "GSTR-3B" in f["description"]
        for f in body["findings"]
    )


def test_drc01c_matched():
    notice = make_notice("synthetic_drc01c_apr2024.txt")
    assert notice["differenceAmount"] == 5000.0
    upload_return(notice["id"], "gstr2b_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_itc_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert body["status"] == "MATCHED", body
    assert body["calculatedDifference"] == 5000.0
    assert body["unexplainedAmount"] == 0.0


def test_drc01c_missing_return_message():
    notice = make_notice("synthetic_drc01c_apr2024.txt")
    upload_return(notice["id"], "gstr2b_matched_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert body["status"] == "MISSING_DATA"
    assert any("GSTR-3B" in f["description"] for f in body["findings"])


def test_period_mismatch_finding_present():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_may_2024-05.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert any(f["category"] == "PERIOD_MISMATCH" for f in body["findings"])


def test_duplicate_invoice_finding():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_duplicate_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    dup = [f for f in body["findings"] if f["category"] == "DUPLICATE_ROW"]
    assert len(dup) == 1
    assert "INV-001" in dup[0]["description"]
    assert len(dup[0]["sourceRows"]) == 2


def test_get_latest_and_get_run():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    created = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    latest = client.get(f"/api/notices/{notice['id']}/reconciliation").json()
    assert latest["id"] == created["id"]
    fetched = client.get(f"/api/reconciliation/{created['id']}").json()
    assert fetched["id"] == created["id"]
    assert fetched["findings"] == created["findings"]


def test_get_reconciliation_before_run_404():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    res = client.get(f"/api/notices/{notice['id']}/reconciliation")
    assert res.status_code == 404


def test_determinism_repeated_execution():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    first = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    second = client.post(f"/api/notices/{notice['id']}/reconciliation").json()

    def canonical(run):
        return {
            "status": run["status"],
            "noticeDifference": run["noticeDifference"],
            "calculatedDifference": run["calculatedDifference"],
            "explainedAmount": run["explainedAmount"],
            "unexplainedAmount": run["unexplainedAmount"],
            "findings": [
                {k: f[k] for k in ("category", "description", "amount", "sourceRows", "status")}
                for f in run["findings"]
            ],
        }

    assert canonical(first) == canonical(second)


def test_traceability_every_finding():
    notice = make_notice("synthetic_drc01b_apr2024.txt")
    upload_return(notice["id"], "gstr1_matched_2024-04.csv")
    upload_return(notice["id"], "gstr3b_matched_2024-04.csv")
    body = client.post(f"/api/notices/{notice['id']}/reconciliation").json()
    assert body["findings"], "expected findings"
    row_ids = {r["id"] for r in database.list_return_rows(notice["id"])}
    for f in body["findings"]:
        assert f["description"], f
        assert f["status"] in ("MATCHED", "MISMATCH", "MISSING_DATA", "PERIOD_MISMATCH", "UNSUPPORTED")
        for ref in f["sourceRows"]:
            assert ref in row_ids, f"dangling source row {ref}"
    totals = [f for f in body["findings"] if f["category"] in ("GSTR1_TOTAL", "GSTR3B_TOTAL")]
    assert len(totals) == 2
    assert sum(1 for _ in totals) == 2
