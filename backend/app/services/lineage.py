"""Evidence lineage: NOTICE -> FINDING -> CALCULATION -> RETURN ROW
-> SOURCE DOCUMENT -> ORIGINAL FILE. Deterministic assembly, no LLM."""

import json
import os

from app import database
from app.parsers import gst_rules
from app.services import storage


def _row_to_dict(r) -> dict:
    try:
        raw = json.loads(r["raw_json"] or "{}")
    except (ValueError, TypeError):
        raw = {}
    return {
        "id": r["id"],
        "returnId": r["return_id"],
        "source": r["source"],
        "period": r["period"],
        "supplierGstin": r["supplier_gstin"],
        "recipientGstin": r["recipient_gstin"],
        "invoiceNumber": r["invoice_number"],
        "invoiceDate": r["invoice_date"],
        "taxableValue": r["taxable_value"],
        "igst": r["igst"],
        "cgst": r["cgst"],
        "sgst": r["sgst"],
        "cess": r["cess"],
        "totalTax": r["total_tax"],
        "creditDebitNote": r["credit_debit_note"],
        "raw": raw,
    }


def _return_doc_to_dict(notice_id: str, r) -> dict:
    path = storage.get_return_file_path(r["id"], r["filename"])
    return {
        "id": r["id"],
        "noticeId": r["notice_id"],
        "source": r["source"],
        "period": r["period"],
        "periodStatus": r["period_status"],
        "filename": r["filename"],
        "rowCount": r["row_count"],
        "status": r["status"],
        "originalFileStored": os.path.exists(path),
        "downloadUrl": f"/api/notices/{notice_id}/return-data/{r['id']}/download",
    }


def get_finding_lineage(finding_id: str) -> dict:
    finding = database.get_finding(finding_id)
    if finding is None:
        raise KeyError(finding_id)

    try:
        source_rows = json.loads(finding["source_rows_json"] or "[]")
    except (ValueError, TypeError):
        source_rows = []
    try:
        inputs = json.loads(finding["inputs_json"] or "{}") if "inputs_json" in finding.keys() else {}
    except (ValueError, TypeError):
        inputs = {}

    run = database.get_run(finding["run_id"])
    if run is None:
        raise KeyError(finding["run_id"])
    notice_row = database.get_notice(finding["notice_id"])
    if notice_row is None:
        raise KeyError(finding["notice_id"])

    notice = {
        "id": notice_row["id"],
        "noticeNumber": notice_row["notice_number"],
        "noticeType": notice_row["notice_type"],
        "taxPeriod": notice_row["tax_period"],
        "differenceAmount": notice_row["difference_amount"],
        "status": notice_row["status"],
    }
    # NOTICE -> SOURCE DOCUMENT (original notice file)
    notice_doc = {
        "id": notice_row["document_id"],
        "filename": notice_row["filename"],
        "mimeType": notice_row["mime_type"],
        "downloadUrl": f"/api/documents/{notice_row['document_id']}/download",
    }

    # FINDING -> RETURN ROW (full row detail, order stable)
    db_rows = database.get_return_rows_by_ids([str(x) for x in source_rows])
    by_id = {r["id"]: r for r in db_rows}
    ordered_rows = [_row_to_dict(by_id[rid]) for rid in [str(x) for x in source_rows] if rid in by_id]

    # RETURN ROW -> SOURCE DOCUMENT (distinct return docs, sorted)
    seen_docs: dict[str, dict] = {}
    for r in ordered_rows:
        ret = database.get_return_document(r["returnId"])
        if ret is not None and ret["id"] not in seen_docs:
            seen_docs[ret["id"]] = _return_doc_to_dict(finding["notice_id"], ret)
    return_docs = [seen_docs[k] for k in sorted(seen_docs)]

    return {
        "finding": {
            "id": finding["id"],
            "runId": finding["run_id"],
            "category": finding["category"],
            "description": finding["description"],
            "amount": finding["amount"],
            "status": finding["status"],
        },
        "calculation": {
            "rule": finding["rule"] if "rule" in finding.keys() else None,
            "formula": finding["formula"] if "formula" in finding.keys() else None,
            "inputs": inputs,
            "ruleVersion": run["rule_version"] or gst_rules.RULE_VERSION,
        },
        "notice": notice,
        "noticeDocument": notice_doc,
        "run": {
            "id": run["id"],
            "status": run["status"],
            "noticeDifference": run["notice_difference"],
            "calculatedDifference": run["calculated_difference"],
            "explainedAmount": run["explained_amount"],
            "unexplainedAmount": run["unexplained_amount"],
            "ruleVersion": run["rule_version"],
        },
        "returnRows": ordered_rows,
        "returnDocuments": return_docs,
        "chain": ["NOTICE", "FINDING", "CALCULATION", "RETURN_ROW", "SOURCE_DOCUMENT", "ORIGINAL_FILE"],
    }


def get_return_rows(notice_id: str, row_ids: list[str], limit: int = 200) -> list[dict]:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    ids = [str(x) for x in (row_ids or [])][:limit]
    db_rows = database.get_return_rows_by_ids(ids)
    by_id = {r["id"]: r for r in db_rows}
    # Only rows belonging to this notice workspace may be returned.
    return [
        _row_to_dict(by_id[rid])
        for rid in ids
        if rid in by_id and by_id[rid]["notice_id"] == notice_id
    ]
