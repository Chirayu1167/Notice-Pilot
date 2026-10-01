# NoticePilot GST

Review-gated GST notice workspace: notice ingestion → deterministic
reconciliation → evidence provenance → agentic review → human approval →
versioned drafts → audit trail → PDF export.

Nothing in this system submits anything to the GST portal or any external
authority. The human reviewer is the final authority.

## Problem

GST mismatch notices (DRC-01B liability mismatches, DRC-01C ITC mismatches)
are difficult for small businesses to reconcile and respond to: return data
lives in spreadsheets, portal intimations are terse, and drafting a reply
means manually tracing every figure back to its source row.

## Solution

NoticePilot walks the full pipeline with provenance at every step:

```
NOTICE → INGEST → PARSE → RECONCILE → EVIDENCE → AGENT → DRAFT
→ HUMAN REVIEW → VERSION → AUDIT → EXPORT
```

- **Deterministic reconciliation** (pure Python, versioned rules for
  CGST Rule 88C / 88D) is the only source of financial truth.
- **Evidence lineage** resolves every finding down to
  NOTICE → FINDING → CALCULATION → RETURN ROW → SOURCE DOCUMENT → ORIGINAL FILE.
- **Agentic review** runs a bounded tool loop (inspect notice, reconcile,
  inspect evidence, detect missing evidence, decide, draft) and replans when
  new evidence arrives.
- **Human review gate**: named demo reviewers approve / request changes /
  reject versioned, immutable drafts. Approvals capture sign-off metadata.
- **Append-only audit trail** records every system, agent, and reviewer action.
- **PDF export**: review PDF plus a portal-ready cover letter (a human-carried
  document — never a filing), both stamped NOT FILED.

## What makes it agentic?

- Explicit tool selection and sequencing (7 backend tools, max 8 iterations).
- Multi-step workflow with a persisted state machine and tool trace.
- Finding-level evidence inspection via lineage tools.
- Missing-evidence detection with structured requirements.
- Replanning: new evidence → reconciliation rerun → fresh agent run over new state.
- Template-backed draft generation with verified citations.
- A hard human-review gate the agent cannot bypass (server-validated).

## Safety

- No autonomous filing, no portal submission, no payments, no e-signatures.
- Human review required; approvals are immutable and sign-off bound.
- Deterministic financial calculations; the LLM only narrates within validated facts.
- Versioned rules (`RULE_VERSION`), immutable evidence/version history.
- Uploaded document text is treated as untrusted data and can never instruct the agent.
- Banned conclusive/filing language is rejected in drafts and edits.

## Run

Backend (from repo root):

    cd backend
    pip install -r requirements.txt
    python -m uvicorn app.main:app --port 8000

Frontend:

    npm install
    npm run dev        # http://localhost:5173

Set `VITE_API_BASE_URL` (see `.env.example`). Default: `http://localhost:8000/api`.

Other scripts:

    npm run build      # typecheck + production build
    npm run typecheck  # tsc --noEmit only

Backend tests:

    cd backend
    python -m pytest tests/ -q

State lives in SQLite plus `backend/storage/` (documents, returns). Override with
`NOTICE_PILOT_STORAGE`. See [backend/Dockerfile](backend/Dockerfile) and
[DEPLOY.md](DEPLOY.md) for deployment.

## Demo (synthetic data only)

Every demo record is labeled `SYNTHETIC DEMO DATA — NOT A REAL GST CASE`.

1. Open the Dashboard — the **Synthetic demo controls** panel appears in demo/dev mode.
2. **Reset synthetic demo** → notice (₹48,260 alleged), returns, PARTIAL
   reconciliation (₹42,100 explained / ₹6,160 unsupported), agent decision
   INSUFFICIENT_EVIDENCE, draft v1.
3. Open the notice: parsed fields, deadline with days remaining, return data,
   agent reasoning with tool trace, missing evidence.
4. **Upload supplemental evidence** → replan → MATCHED (₹48,260 reconciled),
   agent decision CONTEST (still review-gated).
5. Open the draft (Replies): edit → v2 → request changes → edit → v3 → approve
   with sign-off → audit trail → export review PDF and cover letter.
6. Compare v1 → v2 → v3; open historical versions and historical PDFs — they
   keep their original snapshots.

Or run the whole flow headlessly: `POST /api/demo/reset`, then
`POST /api/demo/supplement?notice_id=...` (see `backend/tests/test_acceptance.py`).

Set `VITE_DEMO_MODE=true` (dev default) to show demo controls;
set `DEMO_ENABLED=0` to disable demo endpoints server-side.

## API (selected)

- `POST /api/documents/upload`, `POST /api/notices/parse/{documentId}`
- `POST /api/notices/{id}/return-data`, `POST /api/notices/{id}/reconciliation`
- `GET /api/reconciliation/findings/{id}/lineage`
- `POST /api/notices/{id}/agent/runs`, `POST /api/notices/{id}/agent/replan`
- `GET /api/notices/{id}/review`, `POST /api/drafts/{id}/review`
- `GET /api/drafts/{id}/versions`, `GET /api/drafts/{id}/compare?from_version=&to_version=`
- `GET /api/drafts/{id}/pdf`, `GET /api/drafts/{id}/cover-letter`
- `GET /api/notices/{id}/audit`, `GET /api/reviewers`
- `POST /api/demo/reset`, `POST /api/demo/supplement`
- `GET /api/health`, `GET /api/status`

## Architecture

```
React + Vite + TypeScript (hash routing)
  services/  API clients (api, notices, documents, reconciliation, agent, ...)
  components/  ui · notices · reconciliation · evidence · agent · replies · demo
  pages/  Dashboard · Notices · NoticeDetail · Reconciliation · Evidence ·
          Replies (review workspace) · Settings

FastAPI backend (backend/app)
  api/        documents · notices · returns · reconciliation · agent · review · demo
  services/   extraction · notice_service · storage · reconciliation ·
              return_service · lineage
  parsers/    notice_parser · return parsers (GSTR-1/3B/2B) · gst_rules (versioned)
  agent/      orchestrator · tools · guardrails · provider · prompts · draft ·
              validation · versions · compare · export_validation · pdf ·
              reviewers · safety · demo
  database.py SQLite (WAL), migrations + seed, append-only audit
  storage/    documents/ returns/ notices.db (gitignored)
```

## Testing

165 backend pytest tests (`cd backend && python -m pytest tests/ -q`):

- parsing / extraction / upload validation
- return ingestion, source detection, normalization
- deterministic reconciliation + lineage + traceability
- agent loop, guardrails, replanning, drafts
- reviewers, sign-off, versioning, comparison, historical truth
- validation, review PDF, cover letter, export validation
- security (traversal, malformed files, invalid IDs, injection, bypass)
- demo reset determinism + full 26-step acceptance flow

Frontend: `tsc --noEmit` + `vite build` (no browser E2E harness in repo).

## Limitations

- Synthetic demo data only; no production authentication (demo reviewer identities).
- No live GST portal submission — by design; cover letters are human-carried.
- Notice families limited to DRC-01B / DRC-01C; reconciliation scope is
  SUM-based per the documented rule mappings (no table-level splits, no DRC-03).
- LLM narration only; offline deterministic provider by default.
- Single-user SQLite workspace; no multi-tenancy.

## Future work (out of scope)

GST portal APIs, e-signatures, payments, OCR, messaging integrations,
multi-tenant SaaS, broad legal research, generic chatbot.

## Legacy

The original static prototype is preserved in `legacy-static/`.
