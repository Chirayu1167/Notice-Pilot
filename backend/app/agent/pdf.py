"""PDF export (Phase 5). The generator only formats a fully validated,
structured review packet — it never calculates values.

Packet source of truth per version:
- notice metadata from the database,
- reconciliation numbers from the version's immutable recon snapshot,
- findings/evidence/rule refs from the version row,
- draft text from the version row.
"""

from io import BytesIO

from app import database
from app.agent import versions as versions_mod

NOT_FILED_BANNER = "REVIEW DRAFT \u2014 NOT FILED"
DISCLAIMER = (
    "Review required before submission. "
    "NoticePilot does not submit responses to the GST portal."
)
COVER_PREPARED_BY = "Prepared by NoticePilot for human review and submission."
COVER_NO_SUBMIT = "NoticePilot does not submit this document to the GST portal."
COVER_STATUS_DRAFT = "DRAFT \u2014 HUMAN REVIEW REQUIRED"
COVER_STATUS_APPROVED = "REVIEWED \u2014 READY FOR HUMAN SUBMISSION"


def build_review_packet(draft_id: str, version: int | None = None) -> dict:
    """Assemble the validated structured object the PDF renderer formats."""
    head = database.get_reply_draft(draft_id)
    if head is None:
        raise KeyError(draft_id)
    versions = versions_mod.list_versions(draft_id)
    if version is None:
        version = head["current_version"] or 1
    selected = next((v for v in versions if v["version"] == version), None)
    if selected is None:
        raise LookupError(f"Version {version} not found.")
    notice = database.get_notice(head["notice_id"])
    if notice is None:
        raise KeyError(head["notice_id"])
    snap = selected.get("reconSnapshot") or {}
    if snap.get("ran"):
        try:
            from app.services import reconciliation as recon_service

            recon = recon_service.get_reconciliation_run(snap["runId"])
            findings = [
                {
                    "description": f["description"],
                    "amount": f["amount"],
                    "status": f["status"],
                    "source": ", ".join((f.get("sourceRows") or [])[:5]),
                    "ref": f["id"],
                }
                for f in recon.get("findings") or []
            ]
        except KeyError:
            findings = []
    else:
        findings = []
    returns = database.list_return_documents(head["notice_id"])
    return {
        "draftId": draft_id,
        "version": selected["version"],
        "reviewStatus": selected["reviewStatus"],
        "decision": selected["decision"],
        "createdBy": selected["createdBy"],
        "createdAt": selected["createdAt"],
        "ruleVersion": selected["ruleVersion"],
        "notice": {
            "noticeNumber": notice["notice_number"] or notice["id"],
            "noticeType": notice["notice_type"] or "UNKNOWN",
            "taxPeriod": notice["tax_period"] or "not stated",
            "issueDate": notice["issue_date"],
            "dueDate": notice["due_date"],
            "gstin": notice["gstin"],
        },
        "reconciliation": {
            "noticeDifference": snap.get("noticeDifference"),
            "calculatedDifference": snap.get("calculatedDifference"),
            "explainedAmount": snap.get("explainedAmount"),
            "unexplainedAmount": snap.get("unexplainedAmount"),
            "status": snap.get("status"),
        },
        "findings": findings,
        "evidence": [
            {
                "evidenceId": r["id"],
                "source": r["source"],
                "filename": r["filename"],
                "rowCount": r["row_count"],
            }
            for r in returns
            if r["id"] in set(selected.get("evidenceIds") or [])
        ],
        "content": selected["content"],
    }


def render_pdf(packet: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def inr(value) -> str:
        if value is None:
            return "not stated"
        return f"Rs. {float(value):,.2f}"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title2", parent=styles["Title"], fontSize=16)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10)
    body = ParagraphStyle("Body2", parent=styles["Normal"], fontSize=9, leading=12)
    mono = ParagraphStyle("Mono", parent=styles["Code"] if "Code" in styles else styles["Normal"],
                          fontSize=8, leading=10)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10)

    story = []
    story.append(Paragraph("NOTICEPILOT", title))
    story.append(Paragraph("Review-Ready Response Draft", styles["Heading2"]))
    story.append(Paragraph(NOT_FILED_BANNER, ParagraphStyle(
        "Banner", parent=styles["Normal"], fontSize=11, textColor="red")))
    story.append(Spacer(1, 4 * mm))

    n = packet["notice"]
    story.append(Paragraph("Notice details", h2))
    story.append(Table(
        [["Notice number", n["noticeNumber"]], ["Notice type", n["noticeType"]],
         ["Tax period", n["taxPeriod"]], ["Issue date", n["issueDate"] or "not stated"],
         ["Due date", n["dueDate"] or "not stated"], ["GSTIN", n["gstin"] or "not stated"]],
        colWidths=[45 * mm, 120 * mm],
    ))
    story.append(Spacer(1, 2 * mm))

    r = packet["reconciliation"]
    story.append(Paragraph("Reconciliation summary", h2))
    story.append(Table(
        [["Notice difference", inr(r["noticeDifference"])],
         ["Calculated difference", inr(r["calculatedDifference"])],
         ["Explained amount", inr(r["explainedAmount"])],
         ["Unexplained amount", inr(r["unexplainedAmount"])],
         ["Status", r["status"] or "not run"]],
        colWidths=[45 * mm, 120 * mm],
    ))

    story.append(Paragraph("Findings", h2))
    if packet["findings"]:
        for f in packet["findings"]:
            story.append(Paragraph(
                f"{f['description']} — {inr(f['amount'])} ({f['status']})", body))
            story.append(Paragraph(f"Source: {f['source'] or 'observation'} | Ref: {f['ref']}", mono))
    else:
        story.append(Paragraph("No findings recorded.", body))

    story.append(Paragraph("Evidence references", h2))
    if packet["evidence"]:
        for e in packet["evidence"]:
            story.append(Paragraph(
                f"{e['evidenceId']}: {e['source']} — {e['filename']} ({e['rowCount']} rows)", mono))
    else:
        story.append(Paragraph("No return documents uploaded.", body))

    story.append(Paragraph("Rule references", h2))
    story.append(Paragraph(f"Rule version: {packet['ruleVersion'] or 'unknown'}", mono))

    story.append(Paragraph("Response draft", h2))
    for line in (packet["content"] or "").splitlines():
        story.append(Paragraph(line or "<br/>", body))

    story.append(Paragraph("Review status", h2))
    story.append(Table(
        [["Status", packet["reviewStatus"]], ["Draft version", f"v{packet['version']}"],
         ["Decision", packet["decision"] or "not stated"],
         ["Generated", f"{packet['createdAt']} by {packet['createdBy']}"]],
        colWidths=[45 * mm, 120 * mm],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(DISCLAIMER, small))

    for table in [t for t in story if isinstance(t, Table)]:
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
    doc.build(story)
    return buf.getvalue()


def build_cover_packet(draft_id: str, version: int | None = None) -> dict:
    """Portal-ready cover letter packet. Human-carried document, NOT a filing.

    Built only from an export-validated version; status banner reflects the
    actual review state and never claims filing, submission, or acceptance.
    """
    from app.agent import export_validation as export_mod

    head = database.get_reply_draft(draft_id)
    if head is None:
        raise KeyError(draft_id)
    versions = versions_mod.list_versions(draft_id)
    wanted = version if version is not None else (head["current_version"] or 1)
    if not any(v["version"] == wanted for v in versions):
        raise LookupError(f"Version {wanted} not found.")
    ok, errors, selected = export_mod.validate_version_for_export(draft_id, version)
    if not ok:
        raise ValueError("; ".join(errors))
    assert selected is not None
    head = database.get_reply_draft(draft_id)
    assert head is not None
    notice = database.get_notice(head["notice_id"])
    assert notice is not None
    snap = selected.get("reconSnapshot") or {}
    approved = selected.get("reviewStatus") == "APPROVED"
    review = database.get_review_by_draft(draft_id)
    today = __import__("datetime").date.today().isoformat()
    subject = (
        f"Response to {notice['notice_number'] or notice['id']} "
        f"({notice['notice_type'] or 'GST notice'}) for tax period "
        f"{notice['tax_period'] or 'not stated'}"
    )
    return {
        "draftId": draft_id,
        "version": selected["version"],
        "reviewStatus": selected["reviewStatus"],
        "statusBanner": COVER_STATUS_APPROVED if approved else COVER_STATUS_DRAFT,
        "decision": selected["decision"],
        "date": today,
        "notice": {
            "noticeNumber": notice["notice_number"] or notice["id"],
            "noticeType": notice["notice_type"] or "UNKNOWN",
            "taxPeriod": notice["tax_period"] or "not stated",
            "gstin": notice["gstin"] or "not stated",
        },
        "subject": subject,
        "responseSummary": (
            f"Based on the uploaded records, reconciliation ({snap.get('status') or 'not run'}) "
            f"indicates {_inr(snap.get('explainedAmount'))} explained and "
            f"{_inr(snap.get('unexplainedAmount'))} unexplained of "
            f"{_inr(snap.get('noticeDifference'))}."
        ),
        "reconciliation": {
            "noticeDifference": snap.get("noticeDifference"),
            "explainedAmount": snap.get("explainedAmount"),
            "unexplainedAmount": snap.get("unexplainedAmount"),
            "status": snap.get("status"),
        },
        "findingRefs": selected.get("findingIds") or [],
        "evidenceRefs": selected.get("evidenceIds") or [],
        "ruleReference": f"[Rule {selected.get('ruleVersion') or 'unknown'}]",
        "ruleVersion": selected.get("ruleVersion"),
        "reviewer": {
            "reviewerId": (review["reviewer_id"] if review else ""),
            "reviewerName": (review["reviewer_name"] if review and "reviewer_name" in review.keys() else ""),
        },
        "content": selected.get("content") or "",
    }


def render_cover_pdf(packet: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def inr(value) -> str:
        if value is None:
            return "not stated"
        return f"Rs. {float(value):,.2f}"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CTitle", parent=styles["Title"], fontSize=16)
    h2 = ParagraphStyle("CH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10)
    body = ParagraphStyle("CBody", parent=styles["Normal"], fontSize=9, leading=12)
    mono = ParagraphStyle("CMono", parent=styles["Code"] if "Code" in styles else styles["Normal"],
                          fontSize=8, leading=10)
    small = ParagraphStyle("CSmall", parent=styles["Normal"], fontSize=8, leading=10)

    story = []
    story.append(Paragraph("NOTICEPILOT", title))
    story.append(Paragraph("Cover Letter (portal-ready draft)", styles["Heading2"]))
    story.append(Paragraph(packet["statusBanner"], ParagraphStyle(
        "CBanner", parent=styles["Normal"], fontSize=11, textColor="red")))
    story.append(Spacer(1, 4 * mm))

    n = packet["notice"]
    story.append(Paragraph("Notice details", h2))
    story.append(Table(
        [["Notice number", n["noticeNumber"]], ["GSTIN", n["gstin"]],
         ["Tax period", n["taxPeriod"]], ["Date", packet["date"]]],
        colWidths=[45 * mm, 120 * mm],
    ))
    story.append(Paragraph("Subject", h2))
    story.append(Paragraph(packet["subject"], body))
    story.append(Paragraph("Concise response", h2))
    story.append(Paragraph(packet["responseSummary"], body))

    r = packet["reconciliation"]
    story.append(Paragraph("Reconciliation summary", h2))
    story.append(Table(
        [["Notice difference", inr(r["noticeDifference"])],
         ["Explained amount", inr(r["explainedAmount"])],
         ["Unexplained amount", inr(r["unexplainedAmount"])],
         ["Status", r["status"] or "not run"]],
        colWidths=[45 * mm, 120 * mm],
    ))

    story.append(Paragraph("Finding references", h2))
    for ref in packet["findingRefs"] or ["none recorded"]:
        story.append(Paragraph(ref, mono))
    story.append(Paragraph("Evidence references", h2))
    for ref in packet["evidenceRefs"] or ["none recorded"]:
        story.append(Paragraph(ref, mono))
    story.append(Paragraph("Rule reference / version", h2))
    story.append(Paragraph(
        f"{packet['ruleReference']} (version {packet['ruleVersion'] or 'unknown'})", mono))

    story.append(Paragraph("Reviewer / sign-off status", h2))
    story.append(Table(
        [["Status", packet["reviewStatus"]],
         ["Draft version", f"v{packet['version']}"],
         ["Reviewer", packet["reviewer"]["reviewerName"] or packet["reviewer"]["reviewerId"] or "not reviewed"],
         ["Decision", packet["decision"] or "not stated"]],
        colWidths=[45 * mm, 120 * mm],
    ))

    story.append(Paragraph("Full response text", h2))
    for line in (packet["content"] or "").splitlines():
        story.append(Paragraph(line or "<br/>", body))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(COVER_PREPARED_BY, small))
    story.append(Paragraph(COVER_NO_SUBMIT, small))

    for table in [t for t in story if isinstance(t, Table)]:
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ]))
    doc.build(story)
    return buf.getvalue()


def _inr(value) -> str:
    if value is None:
        return "not stated"
    return f"Rs. {float(value):,.2f}"
