import os
import re

from app import config


def safe_filename(doc_id: str, filename: str) -> str:
    base = os.path.basename(filename or "")
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = base.strip("._") or "upload"
    if len(base) > 120:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 116 - len(ext)] + dot + ext) if dot and len(ext) <= 10 else base[:120]
    return f"{doc_id}_{base}"


def contained_path(base_dir: str, path: str) -> str:
    """Resolve and verify a storage path stays inside its base directory."""
    resolved = os.path.realpath(path)
    base = os.path.realpath(base_dir)
    if resolved != base and not resolved.startswith(base + os.sep):
        raise ValueError("Path escapes storage directory.")
    return resolved


def save_document(doc_id: str, filename: str, content: bytes) -> str:
    os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
    path = os.path.join(config.DOCUMENTS_DIR, safe_filename(doc_id, filename))
    with open(path, "wb") as f:
        f.write(content)
    return path


def get_document_path(doc_id: str, filename: str) -> str:
    return os.path.join(config.DOCUMENTS_DIR, safe_filename(doc_id, filename))


def save_return_file(return_id: str, filename: str, content: bytes) -> str:
    """Persist the original uploaded return file (SOURCE DOCUMENT -> ORIGINAL FILE)."""
    os.makedirs(config.RETURNS_DIR, exist_ok=True)
    path = os.path.join(config.RETURNS_DIR, safe_filename(return_id, filename))
    with open(path, "wb") as f:
        f.write(content)
    return path


def get_return_file_path(return_id: str, filename: str) -> str:
    return os.path.join(config.RETURNS_DIR, safe_filename(return_id, filename))


def validate_upload(filename: str, content: bytes) -> str | None:
    ext = os.path.splitext(filename or "")[1].lower() or "(none)"
    if ext not in config.ALLOWED_EXTENSIONS:
        return f"Unsupported file type '{ext}'. Only PDF and TXT files are accepted."
    if len(content) > config.MAX_FILE_SIZE:
        return "File too large. Maximum size is 10 MB."
    if ext == ".pdf":
        if not content.startswith(b"%PDF"):
            return "Invalid PDF file."
    else:
        if b"\x00" in content[:8192]:
            return "Invalid text file."
        binary_magics = (b"PK\x03\x04", b"MZ", b"\x89PNG", b"\xff\xd8\xff", b"GIF8")
        if any(content.startswith(magic) for magic in binary_magics):
            return "Invalid text file."
    return None
