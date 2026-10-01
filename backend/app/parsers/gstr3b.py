"""GSTR-3B normalizer: summary liability / ITC tables.

Supports the common portal-style layout:
  Nature of supplies | Total Taxable Value | IGST | CGST | SGST | Cess
as well as flat alias layouts (taxable_value, igst, ...).
For DRC-01C the same total_tax sum is used as the ITC-claimed proxy
(Table 4 rows in fixtures carry ITC amounts in the tax columns).
"""

from app.parsers import normalize as n

DESC_ALIASES = {
    "nature_of_supplies", "nature_of_supply", "description", "particulars",
    "supply_nature", "table_description", "details", "supply_type",
    "table", "section", "label",
}
TAXABLE_ALIASES = {
    "total_taxable_value", "taxable_value", "taxable_amt", "taxable_amount",
    "total_taxable_amt", "assessable_value",
}
IGST_ALIASES = {"igst", "integrated_tax", "igst_amount", "igst_amt", "igst_tax"}
CGST_ALIASES = {"cgst", "central_tax", "cgst_amount", "cgst_amt", "cgst_tax"}
SGST_ALIASES = {"sgst", "state_ut_tax", "sgst_amount", "sgst_amt", "sgst_tax", "utgst"}
CESS_ALIASES = {"cess", "cess_amount", "cess_amt", "compensation_cess"}
TOTAL_ALIASES = {
    "total_tax", "total_tax_amount", "tax_amount", "total_gst", "total_amount_of_tax",
}
INVOICE_ALIASES = {"invoice_number", "invoice_no", "reference", "ref_no"}
DATE_ALIASES = {"invoice_date", "date", "return_period", "tax_period", "period"}


def normalize(df, period: str | None, source: str = "GSTR-3B"):
    columns = list(df.columns)
    c_desc = n.find_column(columns, DESC_ALIASES)
    c_taxable = n.find_column(columns, TAXABLE_ALIASES)
    c_igst = n.find_column(columns, IGST_ALIASES)
    c_cgst = n.find_column(columns, CGST_ALIASES)
    c_sgst = n.find_column(columns, SGST_ALIASES)
    c_cess = n.find_column(columns, CESS_ALIASES)
    c_total = n.find_column(columns, TOTAL_ALIASES)
    c_inv = n.find_column(columns, INVOICE_ALIASES)
    c_date = n.find_column(columns, DATE_ALIASES)

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
        taxable = n.parse_number(record.get(c_taxable)) if c_taxable else None
        # Skip fully-empty summary rows (common in portal exports)
        if taxable is None and total is None:
            continue
        raw = {str(k): (None if v != v and isinstance(v, float) else v) for k, v in record.items()}
        desc = record.get(c_desc) if c_desc else None
        rows.append(
            {
                "source": source,
                "period": period,
                "supplier_gstin": None,
                "recipient_gstin": None,
                "invoice_number": n.parse_invoice_no(record.get(c_inv)) if c_inv else None,
                "invoice_date": n.parse_date(record.get(c_date)) if c_date else None,
                "taxable_value": taxable,
                "igst": igst,
                "cgst": cgst,
                "sgst": sgst,
                "cess": cess,
                "total_tax": total,
                "credit_debit_note": str(desc).strip()[:128]
                if desc not in (None, "") else None,
                "raw": raw,
                "_index": idx,
            }
        )
    return rows
