GST_INDICATORS = [
    "GSTIN", "GST ", "GST,", "GST.", "GST)",
    "GOODS AND SERVICES TAX",
    "SHOW CAUSE",
    "DRC-01",
    "TAXABLE",
    "GST PORTAL",
    "TAX AUTHORITY",
    "ASSESSING OFFICER",
    "DEMAND",
]

CORE_FIELDS = (
    "notice_number",
    "gstin",
    "tax_period",
    "issue_date",
    "due_date",
)


def validate(parsed: dict, text: str) -> str:
    upper = text.upper()
    has_gst_context = any(indicator in upper for indicator in GST_INDICATORS)
    extracted = sum(1 for field in CORE_FIELDS if parsed.get(field))

    if not has_gst_context:
        return "UNSUPPORTED"
    if parsed.get("notice_type") == "UNKNOWN":
        return "PARTIAL" if extracted >= 1 else "UNSUPPORTED"
    if extracted >= 3:
        return "VALID"
    return "PARTIAL"
