import os
import sqlite3
import threading

from app import config

_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock:
        conn = connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    extraction_status TEXT NOT NULL DEFAULT 'UPLOADED',
                    extracted_text TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS notices (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id),
                    notice_number TEXT,
                    notice_type TEXT,
                    gstin TEXT,
                    tax_period TEXT,
                    issue_date TEXT,
                    due_date TEXT,
                    difference_amount REAL,
                    requested_action TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS return_documents (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    source TEXT NOT NULL,
                    period TEXT,
                    period_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'READY',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS return_rows (
                    id TEXT PRIMARY KEY,
                    return_id TEXT NOT NULL REFERENCES return_documents(id),
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    source TEXT NOT NULL,
                    period TEXT,
                    supplier_gstin TEXT,
                    recipient_gstin TEXT,
                    invoice_number TEXT,
                    invoice_date TEXT,
                    taxable_value REAL,
                    igst REAL,
                    cgst REAL,
                    sgst REAL,
                    cess REAL,
                    total_tax REAL,
                    credit_debit_note TEXT,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS reconciliation_runs (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    status TEXT NOT NULL,
                    notice_difference REAL,
                    calculated_difference REAL,
                    explained_amount REAL,
                    unexplained_amount REAL,
                    rule_version TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    status TEXT NOT NULL DEFAULT 'IDLE',
                    decision TEXT,
                    reasoning_summary TEXT,
                    requires_review INTEGER NOT NULL DEFAULT 1,
                    provider TEXT,
                    model TEXT,
                    tool_iterations INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    draft_id TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS agent_steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES agent_runs(id),
                    sequence INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    input_json TEXT NOT NULL DEFAULT '{}',
                    output_summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ok',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS reply_drafts (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    agent_run_id TEXT REFERENCES agent_runs(id),
                    decision TEXT,
                    content TEXT NOT NULL DEFAULT '',
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    finding_ids_json TEXT NOT NULL DEFAULT '[]',
                    rule_version TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    requires_review INTEGER NOT NULL DEFAULT 1,
                    current_version INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS draft_versions (
                    id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL REFERENCES reply_drafts(id),
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    decision TEXT,
                    finding_ids_json TEXT NOT NULL DEFAULT '[]',
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    rule_version TEXT,
                    recon_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_by TEXT NOT NULL DEFAULT 'AGENT',
                    agent_run_id TEXT REFERENCES agent_runs(id),
                    parent_version_id TEXT REFERENCES draft_versions(id),
                    review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE (draft_id, version)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    draft_id TEXT NOT NULL REFERENCES reply_drafts(id),
                    version INTEGER NOT NULL DEFAULT 1,
                    reviewer_id TEXT NOT NULL DEFAULT 'reviewer',
                    reviewer_name TEXT NOT NULL DEFAULT '',
                    recon_run_id TEXT,
                    validation_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                    comment TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS reviewers (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'REVIEWER',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    actor_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT '',
                    entity_id TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES reconciliation_runs(id),
                    notice_id TEXT NOT NULL REFERENCES notices(id),
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL,
                    source_rows_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    rule TEXT,
                    formula TEXT,
                    inputs_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            conn.commit()
            _migrate_findings(conn)
            _migrate_reply_drafts(conn)
            _migrate_reviews(conn)
            _seed_reviewers(conn)
        finally:
            conn.close()


def _migrate_findings(conn) -> None:
    """Add lineage columns to pre-existing findings tables (idempotent)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(findings)").fetchall()}
    for column in ("rule TEXT", "formula TEXT", "inputs_json TEXT NOT NULL DEFAULT '{}'"):
        name = column.split(" ")[0]
        if name not in existing:
            conn.execute(f"ALTER TABLE findings ADD COLUMN {column}")
    conn.commit()


def _migrate_reply_drafts(conn) -> None:
    """Add review columns to pre-existing reply_drafts tables (idempotent)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(reply_drafts)").fetchall()}
    for column in ("current_version INTEGER NOT NULL DEFAULT 1",
                   "review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'"):
        name = column.split(" ")[0]
        if name not in existing:
            conn.execute(f"ALTER TABLE reply_drafts ADD COLUMN {column}")
    conn.commit()


def _migrate_reviews(conn) -> None:
    """Add sign-off columns to pre-existing reviews tables (idempotent)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(reviews)").fetchall()}
    for column in ("reviewer_name TEXT NOT NULL DEFAULT ''",
                   "recon_run_id TEXT",
                   "validation_json TEXT NOT NULL DEFAULT '{}'"):
        name = column.split(" ")[0]
        if name not in existing:
            conn.execute(f"ALTER TABLE reviews ADD COLUMN {column}")
    conn.commit()


def _seed_reviewers(conn) -> None:
    """Seed the default synthetic demo reviewer (idempotent)."""
    row = conn.execute(
        "SELECT id FROM reviewers WHERE id = 'reviewer_demo'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO reviewers (id, display_name, role) VALUES (?, ?, ?)",
            ("reviewer_demo", "Demo Reviewer", "REVIEWER"),
        )
    conn.commit()


def create_document(doc_id: str, filename: str, mime_type: str, size: int) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO documents (id, filename, mime_type, size) VALUES (?, ?, ?, ?)",
                (doc_id, filename, mime_type, size),
            )
            conn.commit()
        finally:
            conn.close()


def get_document(doc_id: str):
    conn = connect()
    try:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    finally:
        conn.close()


def update_extraction_status(doc_id: str, status: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute("UPDATE documents SET extraction_status = ? WHERE id = ?", (status, doc_id))
            conn.commit()
        finally:
            conn.close()


def store_extracted_text(doc_id: str, text: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "UPDATE documents SET extracted_text = ?, extraction_status = 'EXTRACTED' WHERE id = ?",
                (text, doc_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_extracted_text(doc_id: str):
    row = get_document(doc_id)
    return row["extracted_text"] if row else None


def create_notice(notice_id: str, doc_id: str, parsed: dict, status: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO notices
                    (id, document_id, notice_number, notice_type, gstin, tax_period,
                     issue_date, due_date, difference_amount, requested_action, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notice_id,
                    doc_id,
                    parsed.get("notice_number"),
                    parsed.get("notice_type"),
                    parsed.get("gstin"),
                    parsed.get("tax_period"),
                    parsed.get("issue_date"),
                    parsed.get("due_date"),
                    parsed.get("difference_amount"),
                    parsed.get("requested_action"),
                    status,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_notice(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT n.*, d.filename, d.mime_type, d.size AS document_size, d.extraction_status
            FROM notices n JOIN documents d ON d.id = n.document_id
            WHERE n.id = ?
            """,
            (notice_id,),
        ).fetchone()
    finally:
        conn.close()


def get_notice_by_document(doc_id: str):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT n.*, d.filename, d.mime_type, d.size AS document_size, d.extraction_status
            FROM notices n JOIN documents d ON d.id = n.document_id
            WHERE n.document_id = ?
            ORDER BY n.created_at DESC LIMIT 1
            """,
            (doc_id,),
        ).fetchone()
    finally:
        conn.close()


def list_notices():
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT n.*, d.filename, d.mime_type, d.size AS document_size, d.extraction_status
            FROM notices n JOIN documents d ON d.id = n.document_id
            ORDER BY n.created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()


# ---- Phase 2: return data + reconciliation ----

def create_return_document(
    return_id: str,
    notice_id: str,
    source: str,
    period: str | None,
    period_status: str,
    filename: str,
    mime_type: str,
    size: int,
    row_count: int,
    status: str = "READY",
) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO return_documents
                    (id, notice_id, source, period, period_status, filename,
                     mime_type, size, row_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (return_id, notice_id, source, period, period_status, filename,
                 mime_type, size, row_count, status),
            )
            conn.commit()
        finally:
            conn.close()


def insert_return_rows(rows: list[dict]) -> None:
    if not rows:
        return
    with _lock:
        conn = connect()
        try:
            conn.executemany(
                """
                INSERT INTO return_rows
                    (id, return_id, notice_id, source, period, supplier_gstin,
                     recipient_gstin, invoice_number, invoice_date, taxable_value,
                     igst, cgst, sgst, cess, total_tax, credit_debit_note, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["id"], r["return_id"], r["notice_id"], r["source"], r.get("period"),
                        r.get("supplier_gstin"), r.get("recipient_gstin"), r.get("invoice_number"),
                        r.get("invoice_date"), r.get("taxable_value"), r.get("igst"), r.get("cgst"),
                        r.get("sgst"), r.get("cess"), r.get("total_tax"),
                        r.get("credit_debit_note"), r.get("raw_json", "{}"),
                    )
                    for r in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()


def list_return_documents(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM return_documents WHERE notice_id = ? ORDER BY created_at ASC",
            (notice_id,),
        ).fetchall()
    finally:
        conn.close()


def list_return_rows(notice_id: str, source: str | None = None):
    conn = connect()
    try:
        if source:
            return conn.execute(
                "SELECT * FROM return_rows WHERE notice_id = ? AND source = ? ORDER BY id ASC",
                (notice_id, source),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM return_rows WHERE notice_id = ? ORDER BY id ASC",
            (notice_id,),
        ).fetchall()
    finally:
        conn.close()


def create_reconciliation_run(
    run_id: str,
    notice_id: str,
    status: str,
    notice_difference,
    calculated_difference,
    explained_amount,
    unexplained_amount,
    rule_version: str,
) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO reconciliation_runs
                    (id, notice_id, status, notice_difference, calculated_difference,
                     explained_amount, unexplained_amount, rule_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, notice_id, status, notice_difference, calculated_difference,
                 explained_amount, unexplained_amount, rule_version),
            )
            conn.commit()
        finally:
            conn.close()


def insert_findings(rows: list[dict]) -> None:
    if not rows:
        return
    with _lock:
        conn = connect()
        try:
            conn.executemany(
                """
                INSERT INTO findings
                    (id, run_id, notice_id, category, description, amount,
                     source_rows_json, status, rule, formula, inputs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (r["id"], r["run_id"], r["notice_id"], r["category"],
                     r["description"], r.get("amount"), r.get("source_rows_json", "[]"),
                     r["status"], r.get("rule"), r.get("formula"), r.get("inputs_json", "{}"))
                    for r in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()


# ---- Phase 4: agent runs, steps, reply drafts ----

def create_agent_run(run_id: str, notice_id: str, status: str,
                     provider: str | None, model: str | None) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO agent_runs (id, notice_id, status, provider, model) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, notice_id, status, provider, model),
            )
            conn.commit()
        finally:
            conn.close()


def update_agent_run(run_id: str, **fields) -> None:
    allowed = {"status", "decision", "reasoning_summary", "requires_review",
               "tool_iterations", "error", "draft_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    if isinstance(updates.get("requires_review"), bool):
        updates["requires_review"] = 1 if updates["requires_review"] else 0
    with _lock:
        conn = connect()
        try:
            if updates.get("status") in ("WAITING_FOR_EVIDENCE", "DRAFT_READY",
                                         "HUMAN_REVIEW", "ERROR"):
                conn.execute(
                    f"UPDATE agent_runs SET {', '.join(f'{k} = ?' for k in updates)}, "
                    f"completed_at = datetime('now') WHERE id = ?",
                    (*updates.values(), run_id),
                )
            else:
                conn.execute(
                    f"UPDATE agent_runs SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                    (*updates.values(), run_id),
                )
            conn.commit()
        finally:
            conn.close()


def get_agent_run(run_id: str):
    conn = connect()
    try:
        return conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        conn.close()


def list_agent_runs(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM agent_runs WHERE notice_id = ? ORDER BY created_at DESC",
            (notice_id,),
        ).fetchall()
    finally:
        conn.close()


def create_agent_step(run_id: str, sequence: int, tool_name: str,
                      tool_input: dict, output_summary: str, status: str) -> None:
    import json as _json
    import uuid as _uuid

    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO agent_steps (id, run_id, sequence, tool_name, input_json, "
                "output_summary, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"step_{_uuid.uuid4().hex[:12]}", run_id, sequence, tool_name,
                 _json.dumps(tool_input, default=str), output_summary, status),
            )
            conn.commit()
        finally:
            conn.close()


def list_agent_steps(run_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM agent_steps WHERE run_id = ? ORDER BY sequence ASC",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()


def create_reply_draft(draft_id: str, notice_id: str, agent_run_id: str | None,
                       decision: str | None, content: str, evidence_ids: list,
                       finding_ids: list, rule_version: str | None,
                       status: str, requires_review: bool) -> None:
    import json as _json

    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO reply_drafts (id, notice_id, agent_run_id, decision, content, "
                "evidence_ids_json, finding_ids_json, rule_version, status, requires_review) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (draft_id, notice_id, agent_run_id, decision, content,
                 _json.dumps(evidence_ids), _json.dumps(finding_ids),
                 rule_version, status, 1 if requires_review else 0),
            )
            conn.commit()
        finally:
            conn.close()


def get_reply_draft(draft_id: str):
    conn = connect()
    try:
        return conn.execute("SELECT * FROM reply_drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        conn.close()


def list_reply_drafts(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reply_drafts WHERE notice_id = ? ORDER BY created_at DESC",
            (notice_id,),
        ).fetchall()
    finally:
        conn.close()


def update_reply_draft(draft_id: str, content: str | None = None,
                       status: str | None = None) -> None:
    updates: dict = {}
    if content is not None:
        updates["content"] = content
    if status is not None:
        updates["status"] = status
    if not updates:
        return
    with _lock:
        conn = connect()
        try:
            conn.execute(
                f"UPDATE reply_drafts SET {', '.join(f'{k} = ?' for k in updates)}, "
                f"updated_at = datetime('now'), requires_review = 1 WHERE id = ?",
                (*updates.values(), draft_id),
            )
            conn.commit()
        finally:
            conn.close()


# ---- Phase 5: immutable draft versions, reviews, audit trail ----

def create_draft_version(version_id: str, draft_id: str, version: int, content: str,
                         decision: str | None, finding_ids: list, evidence_ids: list,
                         rule_version: str | None, recon_snapshot: dict,
                         created_by: str, agent_run_id: str | None,
                         parent_version_id: str | None) -> None:
    import json as _json

    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO draft_versions (id, draft_id, version, content, decision, "
                "finding_ids_json, evidence_ids_json, rule_version, recon_snapshot_json, "
                "created_by, agent_run_id, parent_version_id, review_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_REVIEW')",
                (version_id, draft_id, version, content, decision,
                 _json.dumps(finding_ids), _json.dumps(evidence_ids), rule_version,
                 _json.dumps(recon_snapshot, default=str), created_by, agent_run_id,
                 parent_version_id),
            )
            conn.execute(
                "UPDATE reply_drafts SET content = ?, decision = ?, finding_ids_json = ?, "
                "evidence_ids_json = ?, rule_version = ?, current_version = ?, "
                "review_status = 'PENDING_REVIEW', updated_at = datetime('now'), "
                "requires_review = 1 WHERE id = ?",
                (content, decision, _json.dumps(finding_ids), _json.dumps(evidence_ids),
                 rule_version, version, draft_id),
            )
            conn.commit()
        finally:
            conn.close()


def list_draft_versions(draft_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM draft_versions WHERE draft_id = ? ORDER BY version ASC",
            (draft_id,),
        ).fetchall()
    finally:
        conn.close()


def get_draft_version(draft_id: str, version: int):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM draft_versions WHERE draft_id = ? AND version = ?",
            (draft_id, version),
        ).fetchone()
    finally:
        conn.close()


def set_version_review_status(version_id: str, review_status: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "UPDATE draft_versions SET review_status = ? WHERE id = ?",
                (review_status, version_id),
            )
            conn.commit()
        finally:
            conn.close()


def upsert_review(notice_id: str, draft_id: str, version: int, reviewer_id: str,
                  status: str, comment: str, reviewer_name: str = "",
                  recon_run_id: str | None = None,
                  validation: dict | None = None) -> str:
    import json as _json
    import uuid as _uuid

    with _lock:
        conn = connect()
        try:
            existing = conn.execute(
                "SELECT * FROM reviews WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            if existing is None:
                review_id = f"rev_{_uuid.uuid4().hex[:12]}"
                conn.execute(
                    "INSERT INTO reviews (id, notice_id, draft_id, version, reviewer_id, "
                    "reviewer_name, recon_run_id, validation_json, status, comment) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (review_id, notice_id, draft_id, version, reviewer_id, reviewer_name,
                     recon_run_id, _json.dumps(validation or {}, default=str),
                     status, comment),
                )
            else:
                review_id = existing["id"]
                conn.execute(
                    "UPDATE reviews SET version = ?, reviewer_id = ?, reviewer_name = ?, "
                    "recon_run_id = ?, validation_json = ?, status = ?, "
                    "comment = ?, updated_at = datetime('now') WHERE id = ?",
                    (version, reviewer_id, reviewer_name, recon_run_id,
                     _json.dumps(validation or {}, default=str), status, comment, review_id),
                )
            conn.execute(
                "UPDATE reply_drafts SET review_status = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (status, draft_id),
            )
            conn.commit()
            return review_id
        finally:
            conn.close()


def get_review_by_draft(draft_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reviews WHERE draft_id = ?", (draft_id,)
        ).fetchone()
    finally:
        conn.close()


def list_reviewers():
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reviewers ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
    finally:
        conn.close()


def get_reviewer(reviewer_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reviewers WHERE id = ?", (reviewer_id,)
        ).fetchone()
    finally:
        conn.close()


def create_reviewer(reviewer_id: str, display_name: str, role: str = "REVIEWER") -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO reviewers (id, display_name, role) VALUES (?, ?, ?)",
                (reviewer_id, display_name, role),
            )
            conn.commit()
        finally:
            conn.close()


def create_audit_event(notice_id: str, actor_type: str, actor_id: str, action: str,
                       entity_type: str = "", entity_id: str = "",
                       metadata: dict | None = None) -> str:
    import json as _json
    import uuid as _uuid

    event_id = f"aud_{_uuid.uuid4().hex[:12]}"
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO audit_events (id, notice_id, actor_type, actor_id, action, "
                "entity_type, entity_id, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, notice_id, actor_type, actor_id or "", action,
                 entity_type, entity_id, _json.dumps(metadata or {}, default=str)),
            )
            conn.commit()
            return event_id
        finally:
            conn.close()


def list_audit_events(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM audit_events WHERE notice_id = ? "
            "ORDER BY created_at ASC, rowid ASC",
            (notice_id,),
        ).fetchall()
    finally:
        conn.close()


def list_audit_events_for_entity(entity_type: str, entity_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM audit_events WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY created_at ASC, rowid ASC",
            (entity_type, entity_id),
        ).fetchall()
    finally:
        conn.close()


def find_demo_notices(notice_numbers: list[str], document_filenames: list[str]):
    """Locate synthetic demo workspace notices only. Never matches user data
    unless it literally reuses demo fixture identifiers."""
    if not notice_numbers and not document_filenames:
        return []
    conn = connect()
    try:
        clauses: list[str] = []
        params: list[str] = []
        if notice_numbers:
            clauses.append(f"n.notice_number IN ({','.join('?' for _ in notice_numbers)})")
            params.extend(notice_numbers)
        if document_filenames:
            clauses.append(f"d.filename IN ({','.join('?' for _ in document_filenames)})")
            params.extend(document_filenames)
        return conn.execute(
            "SELECT n.id FROM notices n JOIN documents d ON d.id = n.document_id "
            f"WHERE {' OR '.join(clauses)}",
            params,
        ).fetchall()
    finally:
        conn.close()


def delete_notice_workspace(notice_id: str) -> dict:
    """Delete every row belonging to one notice workspace, in FK-safe order.
    Returns storage file paths for the caller to unlink. No audit event is
    written (the workspace, including its trail, is gone)."""
    from app import config as _config
    from app.services import storage as _storage

    with _lock:
        conn = connect()
        try:
            doc = conn.execute(
                "SELECT document_id FROM notices WHERE id = ?", (notice_id,)
            ).fetchone()
            document_id = doc["document_id"] if doc else None
            ret_docs = conn.execute(
                "SELECT id, filename FROM return_documents WHERE notice_id = ?",
                (notice_id,),
            ).fetchall()
            doc_row = conn.execute(
                "SELECT filename FROM documents WHERE id = ?", (document_id,)
            ).fetchone() if document_id else None
            files = []
            if doc_row:
                files.append((_config.DOCUMENTS_DIR, document_id, doc_row["filename"]))
            for r in ret_docs:
                files.append((_config.RETURNS_DIR, r["id"], r["filename"]))
            draft_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM reply_drafts WHERE notice_id = ?", (notice_id,)).fetchall()]
            run_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM reconciliation_runs WHERE notice_id = ?", (notice_id,)).fetchall()]
            agent_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM agent_runs WHERE notice_id = ?", (notice_id,)).fetchall()]
            for table, col, ids in (
                ("reviews", "draft_id", draft_ids),
                ("draft_versions", "draft_id", draft_ids),
                ("reply_drafts", "notice_id", [notice_id]),
                ("agent_steps", "run_id", agent_ids),
                ("agent_runs", "notice_id", [notice_id]),
                ("findings", "run_id", run_ids),
                ("reconciliation_runs", "notice_id", [notice_id]),
                ("return_rows", "notice_id", [notice_id]),
                ("return_documents", "notice_id", [notice_id]),
                ("notices", "id", [notice_id]),
            ):
                for i in range(0, len(ids), 500):
                    chunk = ids[i:i + 500]
                    if not chunk:
                        continue
                    conn.execute(
                        f"DELETE FROM {table} WHERE {col} IN ({','.join('?' for _ in chunk)})",
                        chunk,
                    )
            conn.execute("DELETE FROM audit_events WHERE notice_id = ?", (notice_id,))
            if document_id:
                conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()
            return {"files": files, "deletedNoticeId": notice_id}
        finally:
            conn.close()


def get_latest_run(notice_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reconciliation_runs WHERE notice_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (notice_id,),
        ).fetchone()
    finally:
        conn.close()


def get_run(run_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM reconciliation_runs WHERE id = ?", (run_id,)
        ).fetchone()
    finally:
        conn.close()


def list_findings(run_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM findings WHERE run_id = ? ORDER BY id ASC", (run_id,)
        ).fetchall()
    finally:
        conn.close()


# ---- Evidence lineage: FINDING -> RETURN ROW -> SOURCE DOCUMENT -> ORIGINAL FILE ----

def get_finding(finding_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
    finally:
        conn.close()


def get_return_document(return_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM return_documents WHERE id = ?", (return_id,)
        ).fetchone()
    finally:
        conn.close()


def get_return_row(row_id: str):
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM return_rows WHERE id = ?", (row_id,)
        ).fetchone()
    finally:
        conn.close()


def get_return_rows_by_ids(row_ids: list[str]):
    if not row_ids:
        return []
    # Chunked to stay within SQLite variable limits; order restored by caller.
    conn = connect()
    try:
        out = []
        for i in range(0, len(row_ids), 500):
            chunk = row_ids[i:i + 500]
            placeholders = ",".join("?" for _ in chunk)
            out.extend(
                conn.execute(
                    f"SELECT * FROM return_rows WHERE id IN ({placeholders})", chunk
                ).fetchall()
            )
        return out
    finally:
        conn.close()
