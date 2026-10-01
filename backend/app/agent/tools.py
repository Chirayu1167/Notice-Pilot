"""Agent tools (Phase 4). Explicit backend tools wrapping the deterministic
Phase 0–3 services. Tools are the ONLY source of facts; the LLM never
computes amounts, invents evidence, or alters reconciliation results."""

from typing import Any

from app import database
from app.agent import schemas
from app.parsers import gst_rules


def _summary(text: str, limit: int = 300) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_get_notice_context(notice_id: str) -> dict[str, Any]:
    from app.agent import safety as safety_mod

    row = database.get_notice(notice_id)
    if row is None:
        raise KeyError(notice_id)
    data = {
        "noticeId": row["id"],
        "noticeNumber": row["notice_number"],
        "noticeType": row["notice_type"],
        "gstin": row["gstin"],
        "taxPeriod": row["tax_period"],
        "issueDate": row["issue_date"],
        "dueDate": row["due_date"],
        "differenceAmount": row["difference_amount"],
        # Free text parsed from the uploaded notice: untrusted data, never
        # instructions. The agent must not follow directions contained in it.
        "requestedAction": safety_mod.mark_untrusted(row["requested_action"]),
        "status": row["status"],
        "sourceDocument": {
            "documentId": row["document_id"],
            "filename": row["filename"],
            "mimeType": row["mime_type"],
        },
    }
    return {
        "data": data,
        "summary": (
            f"Notice {data['noticeNumber'] or data['noticeId']} "
            f"({data['noticeType'] or 'UNKNOWN'}, period {data['taxPeriod'] or 'unknown'}), "
            f"difference Rs. {data['differenceAmount']}."
        ),
    }


def tool_get_reconciliation(notice_id: str) -> dict[str, Any]:
    from app.services import reconciliation as recon_service

    try:
        result = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        return {
            "data": {"ran": False, "reason": "No reconciliation has been run for this notice."},
            "summary": "No reconciliation has been run yet.",
        }
    findings = [
        {
            "id": f["id"],
            "category": f["category"],
            "description": f["description"],
            "amount": f["amount"],
            "status": f["status"],
            "sourceRowCount": len(f.get("sourceRows") or []),
            "calculation": f.get("calculation") or {},
        }
        for f in result.get("findings") or []
    ]
    data = {
        "ran": True,
        "runId": result["id"],
        "status": result["status"],
        "noticeDifference": result["noticeDifference"],
        "calculatedDifference": result["calculatedDifference"],
        "explainedAmount": result["explainedAmount"],
        "unexplainedAmount": result["unexplainedAmount"],
        "ruleVersion": result.get("ruleVersion"),
        "findings": findings,
    }
    return {
        "data": data,
        "summary": (
            f"Reconciliation {data['status']}: Rs. {data['explainedAmount']} explained, "
            f"Rs. {data['unexplainedAmount']} unexplained of Rs. {data['noticeDifference']} "
            f"({len(findings)} findings)."
        ),
    }


def tool_get_finding_lineage(finding_id: str) -> dict[str, Any]:
    from app.services import lineage as lineage_service

    lineage = lineage_service.get_finding_lineage(finding_id)
    data = {
        "findingId": lineage["finding"]["id"],
        "category": lineage["finding"]["category"],
        "amount": lineage["finding"]["amount"],
        "status": lineage["finding"]["status"],
        "calculation": lineage["calculation"],
        "returnRowCount": len(lineage.get("returnRows") or []),
        "returnRowIds": [r["id"] for r in lineage.get("returnRows") or []],
        "returnDocuments": [
            {"id": d["id"], "source": d.get("source"), "filename": d.get("filename"),
             "originalFileStored": d.get("originalFileStored")}
            for d in lineage.get("returnDocuments") or []
        ],
    }
    return {
        "data": data,
        "summary": (
            f"Finding {data['category']} ({data['status']}): {data['returnRowCount']} return rows "
            f"across {len(data['returnDocuments'])} source documents."
        ),
    }


def _evidence_state(notice_id: str) -> dict[str, Any]:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    returns = list(database.list_return_documents(notice_id))
    try:
        from app.services import reconciliation as recon_service

        recon = recon_service.get_latest_reconciliation(notice_id)
    except LookupError:
        recon = None
    verified: list[dict] = []
    partial: list[dict] = []
    for ret in returns:
        entry = {
            "evidenceId": ret["id"],
            "source": ret["source"],
            "period": ret["period"],
            "periodStatus": ret["period_status"],
            "filename": ret["filename"],
            "rowCount": ret["row_count"],
        }
        if (ret["period_status"] or "UNKNOWN") == "MATCH":
            verified.append(entry)
        else:
            partial.append(entry)
    missing = build_missing_evidence(notice_id, returns, recon)
    return {
        "verified": verified,
        "partial": partial,
        "missing": [m.model_dump() if hasattr(m, "model_dump") else m for m in missing],
        "reconciliationStatus": recon["status"] if recon else None,
        "unexplainedAmount": recon["unexplainedAmount"] if recon else None,
    }


def build_missing_evidence(
    notice_id: str, returns: list | None = None, recon: dict | None = None
) -> list[schemas.MissingEvidenceItem]:
    row = database.get_notice(notice_id)
    if row is None:
        raise KeyError(notice_id)
    notice_type = (row["notice_type"] or "UNKNOWN").upper()
    if returns is None:
        returns = list(database.list_return_documents(notice_id))
    if recon is None:
        try:
            from app.services import reconciliation as recon_service

            recon = recon_service.get_latest_reconciliation(notice_id)
        except LookupError:
            recon = None
    present = {r["source"] for r in returns}
    required = gst_rules.REQUIREMENTS.get(notice_type, [])
    missing: list[schemas.MissingEvidenceItem] = []
    for source in sorted(set(required) - present):
        missing.append(
            schemas.MissingEvidenceItem(
                type="RETURN_DOCUMENT",
                source=source,
                period=row["tax_period"],
                reason=f"Required to validate liability difference for {notice_type}.",
            )
        )
    if recon and (recon.get("unexplainedAmount") or 0) > gst_rules.TOLERANCE_INR:
        missing.append(
            schemas.MissingEvidenceItem(
                type="RESIDUAL_AMOUNT",
                period=row["tax_period"],
                amount=recon["unexplainedAmount"],
                reason=(
                    f"Additional supporting document required for the remaining "
                    f"Rs. {recon['unexplainedAmount']:,.2f}."
                ),
            )
        )
    if recon is None:
        missing.append(
            schemas.MissingEvidenceItem(
                type="RECONCILIATION_RUN",
                period=row["tax_period"],
                reason="Run reconciliation before an agent decision can be prepared.",
            )
        )
    for ret in returns:
        if (ret["period_status"] or "UNKNOWN") == "MISMATCH":
            missing.append(
                schemas.MissingEvidenceItem(
                    type="PERIOD_CLARIFICATION",
                    source=ret["source"],
                    period=ret["period"],
                    reason=(
                        f"{ret['source']} period {ret['period'] or 'unknown'} does not match "
                        f"notice period {row['tax_period'] or 'unknown'}."
                    ),
                )
            )
    return missing


def tool_get_evidence(notice_id: str) -> dict[str, Any]:
    state = _evidence_state(notice_id)
    return {
        "data": state,
        "summary": (
            f"Evidence: {len(state['verified'])} verified, {len(state['partial'])} partial, "
            f"{len(state['missing'])} missing."
        ),
    }


def tool_get_missing_evidence(notice_id: str) -> dict[str, Any]:
    if database.get_notice(notice_id) is None:
        raise KeyError(notice_id)
    missing = build_missing_evidence(notice_id)
    data = [m.model_dump() for m in missing]
    first = f" First: {data[0]['reason']}" if data else ""
    return {"data": data, "summary": f"{len(data)} missing evidence items.{first}"}


def tool_rerun_reconciliation(notice_id: str) -> dict[str, Any]:
    from app.services import reconciliation as recon_service

    result = recon_service.run_reconciliation(notice_id)
    return {
        "data": {
            "runId": result["id"],
            "status": result["status"],
            "noticeDifference": result["noticeDifference"],
            "calculatedDifference": result["calculatedDifference"],
            "explainedAmount": result["explainedAmount"],
            "unexplainedAmount": result["unexplainedAmount"],
            "findingCount": len(result.get("findings") or []),
        },
        "summary": (
            f"Re-ran deterministic reconciliation: {result['status']}, "
            f"Rs. {result['explainedAmount']} explained, Rs. {result['unexplainedAmount']} unexplained."
        ),
    }


def tool_generate_reply_draft(notice_id: str, decision: str, run_id: str,
                              explanation: str | None = None) -> dict[str, Any]:
    from app.agent import draft as draft_mod

    draft = draft_mod.build_reply_draft(notice_id, decision, run_id, explanation)
    return {
        "data": {
            "draftId": draft["id"],
            "decision": draft["decision"],
            "requiresReview": draft["requiresReview"],
            "findingIds": draft["findingIds"],
            "evidenceIds": draft["evidenceIds"],
        },
        "summary": (
            f"Reply draft {draft['id']} prepared ({decision}); review required before submission."
        ),
    }


TOOL_PURPOSES = {
    "get_notice_context": "Analyzed notice",
    "get_reconciliation": "Checked reconciliation",
    "get_finding_lineage": "Inspected finding evidence",
    "get_evidence": "Reviewed evidence",
    "get_missing_evidence": "Found missing evidence",
    "rerun_reconciliation": "Re-ran reconciliation",
    "generate_reply_draft": "Decision prepared",
}

TOOLS = {
    "get_notice_context": tool_get_notice_context,
    "get_reconciliation": tool_get_reconciliation,
    "get_finding_lineage": tool_get_finding_lineage,
    "get_evidence": tool_get_evidence,
    "get_missing_evidence": tool_get_missing_evidence,
    "rerun_reconciliation": tool_rerun_reconciliation,
    "generate_reply_draft": tool_generate_reply_draft,
}
