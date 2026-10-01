"""Versioned GST rule / field-mapping module (Phase 2).

Deterministic reconciliation mappings for DRC-01B and DRC-01C.
Researched against official GST/GSTN sources — see SOURCES below.
Update RULE_VERSION when mappings change. No LLM logic lives here.

Documentation date: 2026-09-30
"""

RULE_VERSION = "2026-09-30.v1"

TOLERANCE_INR = 1.0

SOURCES = [
    {
        "notice_type": "DRC-01B",
        "rule": "CGST Rule 88C",
        "relationship": (
            "Tax payable per outward-supplies statement GSTR-1/IFF vs tax payable "
            "per return GSTR-3B for the same tax period. Intimation in Part A of "
            "FORM GST DRC-01B when GSTR-1 liability exceeds GSTR-3B liability by a "
            "configured amount/percentage; taxpayer pays via DRC-03 or explains."
        ),
        "gstr1_fields": "Tables 4A, 4B, 4C, 5, 5A, 6, 7, 9A, 9B, 9C, 10, 11 "
        "(outward supplies other than reverse charge); total tax = IGST+CGST+SGST+Cess",
        "gstr3b_fields": "Table 3.1(a) outward taxable supplies (other than zero-rated, "
        "nil-rated, exempt); total tax = IGST+CGST+SGST+Cess",
        "formula": "calculated_difference = SUM(GSTR-1 total_tax) - SUM(GSTR-3B Table-3.1 total_tax)",
        "urls": [
            "https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/rules/cgst_rules/active/chapter9/rule88c_v1.00.html",
            "https://tutorial.gst.gov.in/downloads/news/return_compliance_in_form_drc_01b.pdf",
            "https://tutorial.gst.gov.in/userguide/returns/FAQs_Return_Compliance.htm",
            "https://tutorial.gst.gov.in/contextualhelp/3BV1/Help_Text_liability_decl_paid.htm",
        ],
    },
    {
        "notice_type": "DRC-01C",
        "rule": "CGST Rule 88D (Notification No. 38/2023-Central Tax dated 04.08.2023)",
        "relationship": (
            "ITC availed in GSTR-3B vs ITC available in auto-drafted statement GSTR-2B "
            "for the same tax period. Intimation in Part A of FORM GST DRC-01C when "
            "ITC claimed in GSTR-3B exceeds ITC available in GSTR-2B by a configured "
            "amount/percentage; taxpayer pays via DRC-03 or explains within 7 days."
        ),
        "gstr2b_fields": "GSTR-2B ITC-available sections (B2B, B2BA, ISD, imports, RCM where "
        "eligible); total ITC = IGST+CGST+SGST+Cess of available credit",
        "gstr3b_fields": "GSTR-3B Table 4 eligible ITC claimed (net of reversals); "
        "total ITC = IGST+CGST+SGST+Cess claimed",
        "formula": "calculated_difference = SUM(GSTR-3B Table-4 ITC claimed) - SUM(GSTR-2B ITC available)",
        "urls": [
            "https://tutorial.gst.gov.in/downloads/news/new_functionalities_compilation_april_2023_march_2024.pdf",
            "https://tutorial.gst.gov.in/userguide/returns/Manual_Return_Compliance_ITC.htm",
            "https://cleartax.in/s/rule-88d-cgst-itc-mismatch-gstr-2b-vs-gstr-3b",
        ],
    },
]

# Simplified engine scope (deliberately narrow):
# - DRC-01B requires GSTR-1 + GSTR-3B. Compares SUM(total_tax) per source.
# - DRC-01C requires GSTR-2B + GSTR-3B. Compares SUM(total_tax) as ITC proxy.
# - Table-level splits (3.1(a) vs 3.1(d), exports, RCM, reversals) are NOT modelled
#   in v1; fixtures use plain domestic taxable rows so SUM(total_tax) is exact.
# - DRC-03 payments are NOT modelled in v1 (no fixture, no double-counting).

REQUIREMENTS = {
    "DRC-01B": ["GSTR-1", "GSTR-3B"],
    "DRC-01C": ["GSTR-2B", "GSTR-3B"],
}
