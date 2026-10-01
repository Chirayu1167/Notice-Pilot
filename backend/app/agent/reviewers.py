"""Named reviewer identities (Phase 6). Lightweight demo identities — this is
NOT production authentication. Every review action records reviewer_id,
reviewer display name, timestamp, and action in the audit trail."""

import re

from app import database

REVIEWER_ID_RE = re.compile(r"^[a-z0-9_]{1,32}$")

DEFAULT_REVIEWER_ID = "reviewer_demo"


def valid_reviewer_id(value: str) -> bool:
    return bool(REVIEWER_ID_RE.match(value or ""))


def list_reviewers() -> list[dict]:
    return [
        {"id": r["id"], "displayName": r["display_name"], "role": r["role"],
         "createdAt": r["created_at"]}
        for r in database.list_reviewers()
    ]


def get_reviewer_or_raise(reviewer_id: str) -> dict:
    row = database.get_reviewer(reviewer_id)
    if row is None:
        raise KeyError(reviewer_id)
    return {"id": row["id"], "displayName": row["display_name"], "role": row["role"],
            "createdAt": row["created_at"]}


def create_reviewer(reviewer_id: str, display_name: str) -> dict:
    reviewer_id = (reviewer_id or "").strip().lower()
    display_name = (display_name or "").strip()
    if not valid_reviewer_id(reviewer_id):
        raise ValueError(
            "Reviewer id must be 1-32 lowercase letters, digits, or underscores."
        )
    if not display_name or len(display_name) > 80:
        raise ValueError("Display name must be 1-80 characters.")
    if database.get_reviewer(reviewer_id) is not None:
        raise ValueError(f"Reviewer '{reviewer_id}' already exists.")
    database.create_reviewer(reviewer_id, display_name, "REVIEWER")
    return get_reviewer_or_raise(reviewer_id)
