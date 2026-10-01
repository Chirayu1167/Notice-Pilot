"""GSTR-2B normalizer: auto-drafted ITC (invoice-level inward supplies)."""

from app.parsers import normalize as n

SUPPLIER_ALIASES = {
    "supplier_gstin", "supplier_gstin_uin", "gstin_of_supplier", "gstin_supplier",
    "supplier", "seller_gstin", "vendor_gstin", "gstin_uin_of_supplier", "gstin",
}
INVOICE_ALIASES = {
    "invoice_number", "invoice_no", "inv_no", "document_number", "doc_number",
    "bill_of_entry", "invoice", "bill_number",
}
DATE_ALIASES = {
    "invoice_date", "invoice_dt", "inv_date", "document_date", "doc_date", "date",
    "bill_date",
}
TAXABLE_ALIASES = {
    "taxable_value", "taxable_amt", "taxable_amount", "assessable_value",
    "invoice_value", "total_taxable_value",
}
IGST_ALIASES = {"igst", "igst_amount", "igst_amt", "integrated_tax", "itc_igst"}
CGST_ALIASES = {"cgst", "cgst_amount", "cgst_amt", "central_tax", "itc_cgst"}
SGST_ALIASES = {"sgst", "sgst_amount", "sgst_amt", "state_tax", "utgst", "itc_sgst"}
CESS_ALIASES = {"cess", "cess_amount", "cess_amt", "itc_cess"}
TOTAL_ALIASES = {
    "itc_available", "total_itc", "itc_amount", "available_itc", "total_tax",
    "tax_amount", "total_gst",
}
NOTE_ALIASES = {
    "itc_availability", "availability", "section", "table", "type",
    "document_type", "supply_type", "note_type",
}


def normalize(df, period: str | None, source: str = "GSTR-2B"):
    columns = list(df.columns)
    c_sup = n.find_column(columns, SUPPLIER_ALIASES)
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
                "supplier_gstin": n.parse_gstin(record.get(c_sup)) if c_sup else None,
                "recipient_gstin": None,
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
