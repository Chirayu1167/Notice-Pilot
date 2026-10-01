"""Deterministic reconciliation engine (Phase 2). Pure Python, no LLM, no I/O.

Inputs: notice row dict + normalized return rows.
Outputs: ReconciliationResult dict with explainable, traceable findings.

Rules versioned in app.parsers.gst_rules.
"""

import json
import uuid

from app import database
from app.parsers import gst_rules


def _round2(value) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _sum_tax(rows: list[dict]) -> float:
    total = 0.0
    for r in rows:
        v = r.get("total_tax")
        if v is None:
            continue
        total += float(v)
    return round(total, 2)


def _row_ids(rows: list[dict], limit: int = 50) -> list[str]:
    ids = sorted(str(r["id"]) for r in rows)
    return ids[:limit]


def run_reconciliation(notice_id: str) -> dict:
    notice = database.get_notice(notice_id)
    if notice is None:
        raise KeyError(notice_id)
    notice_type = (notice["notice_type"] or "UNKNOWN").upper()
    notice_diff = _round2(notice["difference_amount"]) or 0.0

    returns = list(database.list_return_documents(notice_id))
    rows = [dict(r) for r in database.list_return_rows(notice_id)]

    by_source: dict[str, list[dict]] = {}
    for r in rows:
        by_source.setdefault(r["source"], []).append(r)

    required = gst_rules.REQUIREMENTS.get(notice_type, [])
    findings: list[dict] = []
    status = "UNEXPLAINED"
    calculated = 0.0
    explained = 0.0

    def add(
        category: str,
        description: str,
        amount,
        source_rows: list[str],
        fstatus: str,
        calculation: dict | None = None,
    ):
        findings.append(
            {
                "category": category,
                "description": description,
                "amount": _round2(amount),
                "source_rows": sorted(source_rows),
                "status": fstatus,
                "calculation": calculation or {
                    "rule": "RECONCILIATION ENGINE",
                    "formula": "observation (no arithmetic)",
                    "inputs": {},
                    "ruleVersion": gst_rules.RULE_VERSION,
                },
            }
        )

    def total_calc(label: str, total: float, count: int) -> dict:
        return {
            "rule": "RECONCILIATION ENGINE",
            "formula": f"SUM(total_tax) over {count} {label} rows",
            "inputs": {"source": label, "rowCount": count, "totalTax": _round2(total)},
            "ruleVersion": gst_rules.RULE_VERSION,
        }

    # Period observations (never block the run, always reported)
    for ret in returns:
        ps = ret["period_status"] or "UNKNOWN"
        if ps == "MISMATCH":
            add(
                "PERIOD_MISMATCH",
                f"{ret['source']} period {ret['period'] or 'unknown'} does not match "
                f"notice period {notice['tax_period'] or 'unknown'}.",
                None,
                _row_ids([r for r in rows if r["return_id"] == ret["id"]], limit=5),
                "MISMATCH",
                {
                    "rule": "RECONCILIATION ENGINE",
                    "formula": "compare_period(notice.taxPeriod, return.period)",
                    "inputs": {
                        "noticePeriod": notice["tax_period"],
                        "returnPeriod": ret["period"],
                        "returnSource": ret["source"],
                        "result": "MISMATCH",
                    },
                    "ruleVersion": gst_rules.RULE_VERSION,
                },
            )
        elif ps == "UNKNOWN":
            add(
                "PERIOD_UNKNOWN",
                f"{ret['source']} period could not be validated against notice period "
                f"{notice['tax_period'] or 'unknown'}.",
                None,
                [],
                "MISSING_DATA",
                {
                    "rule": "RECONCILIATION ENGINE",
                    "formula": "compare_period(notice.taxPeriod, return.period)",
                    "inputs": {
                        "noticePeriod": notice["tax_period"],
                        "returnPeriod": ret["period"],
                        "returnSource": ret["source"],
                        "result": "UNKNOWN",
                    },
                    "ruleVersion": gst_rules.RULE_VERSION,
                },
            )

    # Duplicate invoice detection (within GSTR-1 / GSTR-2B invoice-level sources)
    for src in ("GSTR-1", "GSTR-2B"):
        seen: dict[str, list[str]] = {}
        for r in by_source.get(src, []):
            inv = (r.get("invoice_number") or "").strip()
            if inv:
                seen.setdefault(inv, []).append(str(r["id"]))
        for inv in sorted(seen):
            if len(seen[inv]) > 1:
                add(
                    "DUPLICATE_ROW",
                    f"Duplicate invoice {inv} appears {len(seen[inv])} times in {src}; "
                    f"both rows are included in totals.",
                    None,
                    sorted(seen[inv]),
                    "MISMATCH",
                    {
                        "rule": "RECONCILIATION ENGINE",
                        "formula": "COUNT(rows GROUP BY invoice_number) HAVING COUNT > 1",
                        "inputs": {"source": src, "invoiceNumber": inv, "occurrences": len(seen[inv])},
                        "ruleVersion": gst_rules.RULE_VERSION,
                    },
                )

    if notice_type == "DRC-01B":
        g1 = by_source.get("GSTR-1", [])
        g3 = by_source.get("GSTR-3B", [])
        missing = [s for s in required if not by_source.get(s)]
        presence_calc = {
            "rule": "RECONCILIATION ENGINE",
            "formula": "required-sources presence check",
            "inputs": {
                "noticeType": "DRC-01B",
                "required": sorted(required),
                "present": sorted(by_source.keys()),
            },
            "ruleVersion": gst_rules.RULE_VERSION,
        }
        compare_calc = lambda t1, t3, calc: {
            "rule": "CGST Rule 88C",
            "formula": "SUM(GSTR-1 total_tax) - SUM(GSTR-3B total_tax)",
            "inputs": {
                "gstr1Total": t1, "gstr1Rows": len(g1),
                "gstr3bTotal": t3, "gstr3bRows": len(g3),
                "calculatedDifference": calc,
                "noticeDifference": notice_diff,
                "toleranceInr": gst_rules.TOLERANCE_INR,
            },
            "ruleVersion": gst_rules.RULE_VERSION,
        }
        if missing:
            for s in sorted(missing):
                add(
                    "MISSING_DATA",
                    f"Upload {s} for the notice period to run this reconciliation.",
                    None, [], "MISSING_DATA",
                    presence_calc,
                )
            calculated = 0.0
            explained = 0.0
            status = "MISSING_DATA" if not findings or all(
                f["category"] in ("MISSING_DATA", "PERIOD_MISMATCH", "PERIOD_UNKNOWN", "DUPLICATE_ROW")
                for f in findings
            ) else "UNEXPLAINED"
            # Still record component totals for whatever is present
            if g1:
                add("GSTR1_TOTAL", f"Total tax as per GSTR-1 across {len(g1)} rows.", _sum_tax(g1), _row_ids(g1), "MATCHED", total_calc("GSTR-1", _sum_tax(g1), len(g1)))
            if g3:
                add("GSTR3B_TOTAL", f"Total liability as per GSTR-3B across {len(g3)} rows.", _sum_tax(g3), _row_ids(g3), "MATCHED", total_calc("GSTR-3B", _sum_tax(g3), len(g3)))
        else:
            t1, t3 = _sum_tax(g1), _sum_tax(g3)
            calculated = round(t1 - t3, 2)
            add("GSTR1_TOTAL", f"Total tax as per GSTR-1 across {len(g1)} rows.", t1, _row_ids(g1), "MATCHED", total_calc("GSTR-1", t1, len(g1)))
            add("GSTR3B_TOTAL", f"Total liability as per GSTR-3B across {len(g3)} rows.", t3, _row_ids(g3), "MATCHED", total_calc("GSTR-3B", t3, len(g3)))
            diff_vs_notice = round(abs(calculated - notice_diff), 2)
            if diff_vs_notice <= gst_rules.TOLERANCE_INR:
                explained = calculated
                status = "MATCHED"
                add(
                    "MATCHED_COMPONENT",
                    f"GSTR-1 (Rs. {t1:,.2f}) minus GSTR-3B (Rs. {t3:,.2f}) = Rs. {calculated:,.2f}, "
                    f"matches notice difference Rs. {notice_diff:,.2f} within Rs. {gst_rules.TOLERANCE_INR:.2f}.",
                    calculated, _row_ids(g1 + g3), "MATCHED",
                    compare_calc(t1, t3, calculated),
                )
            else:
                explained = calculated
                status = "PARTIAL" if calculated != 0 else "UNEXPLAINED"
                add(
                    "MISMATCH",
                    f"GSTR-1 (Rs. {t1:,.2f}) minus GSTR-3B (Rs. {t3:,.2f}) = Rs. {calculated:,.2f}; "
                    f"notice states Rs. {notice_diff:,.2f}. Residual Rs. {round(notice_diff - calculated, 2):,.2f} unexplained.",
                    calculated, _row_ids(g1 + g3), "MISMATCH",
                    compare_calc(t1, t3, calculated),
                )
    elif notice_type == "DRC-01C":
        g2 = by_source.get("GSTR-2B", [])
        g3 = by_source.get("GSTR-3B", [])
        missing = [s for s in required if not by_source.get(s)]
        presence_calc = {
            "rule": "RECONCILIATION ENGINE",
            "formula": "required-sources presence check",
            "inputs": {
                "noticeType": "DRC-01C",
                "required": sorted(required),
                "present": sorted(by_source.keys()),
            },
            "ruleVersion": gst_rules.RULE_VERSION,
        }
        compare_calc = lambda t2, t3, calc: {
            "rule": "CGST Rule 88D",
            "formula": "SUM(GSTR-3B Table-4 ITC claimed) - SUM(GSTR-2B ITC available)",
            "inputs": {
                "gstr2bTotal": t2, "gstr2bRows": len(g2),
                "gstr3bTotal": t3, "gstr3bRows": len(g3),
                "calculatedDifference": calc,
                "noticeDifference": notice_diff,
                "toleranceInr": gst_rules.TOLERANCE_INR,
            },
            "ruleVersion": gst_rules.RULE_VERSION,
        }
        if missing:
            for s in sorted(missing):
                add(
                    "MISSING_DATA",
                    f"Upload {s} for the notice period to run this reconciliation.",
                    None, [], "MISSING_DATA",
                    presence_calc,
                )
            if g2:
                add("GSTR2B_TOTAL", f"Total ITC available as per GSTR-2B across {len(g2)} rows.", _sum_tax(g2), _row_ids(g2), "MATCHED", total_calc("GSTR-2B", _sum_tax(g2), len(g2)))
            if g3:
                add("GSTR3B_TOTAL", f"Total ITC claimed as per GSTR-3B across {len(g3)} rows.", _sum_tax(g3), _row_ids(g3), "MATCHED", total_calc("GSTR-3B", _sum_tax(g3), len(g3)))
            status = "MISSING_DATA"
            calculated, explained = 0.0, 0.0
        else:
            t2, t3 = _sum_tax(g2), _sum_tax(g3)
            calculated = round(t3 - t2, 2)
            add("GSTR2B_TOTAL", f"Total ITC available as per GSTR-2B across {len(g2)} rows.", t2, _row_ids(g2), "MATCHED", total_calc("GSTR-2B", t2, len(g2)))
            add("GSTR3B_TOTAL", f"Total ITC claimed as per GSTR-3B across {len(g3)} rows.", t3, _row_ids(g3), "MATCHED", total_calc("GSTR-3B", t3, len(g3)))
            diff_vs_notice = round(abs(calculated - notice_diff), 2)
            if diff_vs_notice <= gst_rules.TOLERANCE_INR:
                explained = calculated
                status = "MATCHED"
                add(
                    "MATCHED_COMPONENT",
                    f"GSTR-3B ITC (Rs. {t3:,.2f}) minus GSTR-2B available (Rs. {t2:,.2f}) = Rs. {calculated:,.2f}, "
                    f"matches notice difference Rs. {notice_diff:,.2f} within Rs. {gst_rules.TOLERANCE_INR:.2f}.",
                    calculated, _row_ids(g2 + g3), "MATCHED",
                    compare_calc(t2, t3, calculated),
                )
            else:
                explained = calculated
                status = "PARTIAL" if calculated != 0 else "UNEXPLAINED"
                add(
                    "MISMATCH",
                    f"GSTR-3B ITC (Rs. {t3:,.2f}) minus GSTR-2B available (Rs. {t2:,.2f}) = Rs. {calculated:,.2f}; "
                    f"notice states Rs. {notice_diff:,.2f}. Residual Rs. {round(notice_diff - calculated, 2):,.2f} unexplained.",
                    calculated, _row_ids(g2 + g3), "MISMATCH",
                    compare_calc(t2, t3, calculated),
                )
    else:
        add(
            "UNSUPPORTED",
            f"Notice type {notice_type} is not supported by the Phase-2 reconciliation engine "
            f"(supports DRC-01B and DRC-01C only).",
            None, [], "UNSUPPORTED",
        )
        status = "UNSUPPORTED"
        calculated, explained = 0.0, 0.0

    unexplained = round(notice_diff - explained, 2)

    # Deterministic ordering + deterministic finding ids
    findings_sorted = sorted(findings, key=lambda f: (f["category"], f["description"]))
    run_id = f"recon_{uuid.uuid4().hex[:12]}"
    database.create_reconciliation_run(
        run_id, notice_id, status, notice_diff, calculated,
        explained, unexplained, gst_rules.RULE_VERSION,
    )
    db_findings = []
    for i, f in enumerate(findings_sorted):
        db_findings.append(
            {
                "id": f"{run_id}-f{i + 1:03d}",
                "run_id": run_id,
                "notice_id": notice_id,
                "category": f["category"],
                "description": f["description"],
                "amount": f["amount"],
                "source_rows_json": json.dumps(f["source_rows"]),
                "status": f["status"],
                "rule": f["calculation"].get("rule"),
                "formula": f["calculation"].get("formula"),
                "inputs_json": json.dumps(f["calculation"].get("inputs") or {}, sort_keys=True),
            }
        )
    database.insert_findings(db_findings)

    return _run_to_dict(run_id, notice_id, status, notice_diff, calculated, explained, unexplained, db_findings)


def get_latest_reconciliation(notice_id: str) -> dict:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    run = database.get_latest_run(notice_id)
    if run is None:
        raise LookupError("No reconciliation has been run for this notice.")
    return get_reconciliation_run(run["id"])


def get_reconciliation_run(run_id: str) -> dict:
    run = database.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    rows = database.list_findings(run_id)
    db_findings = [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "notice_id": r["notice_id"],
            "category": r["category"],
            "description": r["description"],
            "amount": r["amount"],
            "source_rows_json": r["source_rows_json"],
            "status": r["status"],
            "rule": r["rule"] if "rule" in r.keys() else None,
            "formula": r["formula"] if "formula" in r.keys() else None,
            "inputs_json": r["inputs_json"] if "inputs_json" in r.keys() else "{}",
        }
        for r in rows
    ]
    return _run_to_dict(
        run["id"], run["notice_id"], run["status"], run["notice_difference"],
        run["calculated_difference"], run["explained_amount"],
        run["unexplained_amount"], db_findings,
    )


def _run_to_dict(run_id, notice_id, status, notice_diff, calculated, explained, unexplained, db_findings) -> dict:
    findings = []
    for f in sorted(db_findings, key=lambda x: x["id"]):
        try:
            source_rows = json.loads(f.get("source_rows_json") or "[]")
        except (ValueError, TypeError):
            source_rows = []
        try:
            inputs = json.loads(f.get("inputs_json") or "{}")
        except (ValueError, TypeError):
            inputs = {}
        findings.append(
            {
                "id": f["id"],
                "category": f["category"],
                "description": f["description"],
                "amount": f["amount"],
                "sourceRows": source_rows,
                "status": f["status"],
                "calculation": {
                    "rule": f.get("rule"),
                    "formula": f.get("formula"),
                    "inputs": inputs,
                    "ruleVersion": gst_rules.RULE_VERSION,
                },
            }
        )
    return {
        "id": run_id,
        "noticeId": notice_id,
        "status": status,
        "noticeDifference": notice_diff,
        "calculatedDifference": calculated,
        "explainedAmount": explained,
        "unexplainedAmount": unexplained,
        "ruleVersion": gst_rules.RULE_VERSION,
        "findings": findings,
    }
