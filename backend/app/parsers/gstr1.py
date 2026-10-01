"""GSTR-1 normalizer: outward supplies (invoice-level rows)."""

from app.parsers import normalize as n

GSTIN_ALIASES = {
    "gstin_uin_of_recipient", "gstin_uin_recipient", "recipient_gstin",
    "gstin_uin", "receiver_gstin", "buyer_gstin", "gstin",
}
INVOICE_ALIASES = {
    "invoice_number", "invoice_no", "inv_no", "invoice_num", "document_number",
    "doc_number", "invoice", "bill_number",
}
DATE_ALIASES = {
    "invoice_date", "invoice_dt", "inv_date", "document_date", "doc_date", "date",
}
TAXABLE_ALIASES = {
    "taxable_value", "taxable_amt", "taxable_amount", "assessable_value",
    "invoice_value_taxable", "total_taxable_value",
}
IGST_ALIASES = {"igst", "igst_amount", "igst_amt", "integrated_tax", "igst_tax"}
CGST_ALIASES = {"cgst", "cgst_amount", "cgst_amt", "central_tax", "cgst_tax"}
SGST_ALIASES = {"sgst", "sgst_amount", "sgst_amt", "state_tax", "utgst", "sgst_utgst", "sgst_tax"}
CESS_ALIASES = {"cess", "cess_amount", "cess_amt", "compensation_cess"}
TOTAL_ALIASES = {
    "total_tax", "total_tax_amount", "tax_amount", "total_gst", "total_tax_value",
    "invoice_tax", "tax_payable",
}
NOTE_ALIASES = {
    "note_type", "document_type", "type", "supply_type", "note_supply_type",
    "debit_credit_note", "table", "section",
}


def normalize(df, period: str | None, source: str = "GSTR-1"):
    columns = list(df.columns)
    c_gstin = n.find_column(columns, GSTIN_ALIASES)
    c_inv = n.find_column(columns, INVOICE_ALIASES)
    c_date = n.find_column(columns, DATE_ALIASES)
    c_taxable = n.find_column(columns, TAXABLE_ALIASES)
    c_igst = n.find_column(columns, IGST_ALIASES)
    c_cgst = n.find_column(columns, CGST_ALIASES)
    c_sgst = n.find_column(columns, SGST_ALIASES)
    c_cess = n.find_column(columns, CESS_ALIASES)
    c_total = n.find_column(columns, TOTAL_ALIASES)
    c_note = n.find_column(columns, NOTE_ALIASES)

    rows = []
    for idx, record in enumerate(df.to_dict(orient="records")):
        igst = n.parse_number(record.get(c_igst)) if c_igst else None
        cgst = n.parse_number(record.get(c_cgst)) if c_cgst else None
        sgst = n.parse_number(record.get(c_sgst)) if c_sgst else None
        cess = n.parse_number(record.get(c_cess)) if c_cess else None
        total = n.parse_number(record.get(c_total)) if c_total else None
        if total is None:
            parts = [v for v in (igst, cgst, sgst, cess) if v is not None]
            total = round(sum(parts), 2) if parts else None
        raw = {str(k): (None if v != v and isinstance(v, float) else v) for k, v in record.items()}
        rows.append(
            {
                "source": source,
                "period": period,
                "supplier_gstin": None,
                "recipient_gstin": n.parse_gstin(record.get(c_gstin)) if c_gstin else None,
                "invoice_number": n.parse_invoice_no(record.get(c_inv)) if c_inv else None,
                "invoice_date": n.parse_date(record.get(c_date)) if c_date else None,
                "taxable_value": n.parse_number(record.get(c_taxable)) if c_taxable else None,
                "igst": igst,
                "cgst": cgst,
                "sgst": sgst,
                "cess": cess,
                "total_tax": total,
                "credit_debit_note": str(record.get(c_note)).strip()[:64]
                if c_note and record.get(c_note) not in (None, "") else None,
                "raw": raw,
                "_index": idx,
            }
        )
    return rows
