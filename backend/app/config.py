import os

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Overridable so deployments (e.g. Docker volumes) can relocate state.
STORAGE_DIR = os.environ.get("NOTICE_PILOT_STORAGE") or os.path.join(BACKEND_ROOT, "storage")
DOCUMENTS_DIR = os.path.join(STORAGE_DIR, "documents")
RETURNS_DIR = os.path.join(STORAGE_DIR, "returns")
DB_PATH = os.path.join(STORAGE_DIR, "notices.db")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".txt": "text/plain"}

# Phase 2: structured return data (CSV/XLSX only — deliberately narrow)
RETURN_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
RETURN_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
RETURN_MAX_ROWS = 50000
