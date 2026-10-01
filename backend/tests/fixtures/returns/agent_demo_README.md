# SYNTHETIC DEMO DATA — NOT A REAL GST CASE

End-to-end Phase 4 walkthrough. Every number below is fictitious and
internally consistent.

## Setup

1. Upload `../synthetic_drc01b_48260.txt` as a notice and parse it.
   Notice difference: **Rs. 48,260.00**, DRC-01B, period 2025-07.
2. Upload `agent_gstr1_initial_2025-07.csv` (GSTR-1, tax Rs. 1,00,000.00).
3. Upload `agent_gstr3b_2025-07.csv` (GSTR-3B, liability Rs. 57,900.00).
4. Run reconciliation → **PARTIAL**: explained Rs. 42,100.00,
   unexplained Rs. 6,160.00.

## Agent run 1

5. Run the agent review. Expected decision: **INSUFFICIENT_EVIDENCE**,
   status WAITING_FOR_EVIDENCE, missing evidence:
   "Additional supporting document required for the remaining Rs. 6,160.00."
6. A review-only reply draft is generated with citations
   ([Finding …], [Evidence …], [Rule 88C / 2026-09-30.v1]).

## Re-planning

7. Upload `agent_gstr1_supplemental_2025-07.csv`
   (late GSTR-1 invoice, tax Rs. 6,160.00) via "Upload missing evidence".
8. The system reruns deterministic reconciliation (**MATCHED**:
   Rs. 48,260.00 fully explained) and runs the agent again over the
   updated state — nothing is simulated.
9. Expected decision: **CONTEST** (records reconcile; demand contested),
   still marked as an agent-generated review decision requiring human
   review — never an automatic legal conclusion.
