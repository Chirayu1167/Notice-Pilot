"""Draft version comparison (Phase 6). Document-oriented diff over stored
immutable versions — history is never reconstructed from the current draft."""

import difflib

from app import database
from app.agent import versions as versions_mod


def _content_diff(old: str, new: str, limit: int = 400) -> list[dict]:
    """Line diff with added/removed/changed classification (capped)."""
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    changes: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if len(changes) >= limit:
            changes.append({"kind": "truncated", "note": f"Diff capped at {limit} hunks."})
            break
        if tag == "delete":
            changes.append({"kind": "removed", "old": old_lines[i1:i2], "new": []})
        elif tag == "insert":
            changes.append({"kind": "added", "old": [], "new": new_lines[j1:j2]})
        else:
            changes.append({"kind": "changed", "old": old_lines[i1:i2], "new": new_lines[j1:j2]})
    return changes


def _snap_numbers(snap: dict) -> dict:
    return {
        "status": snap.get("status"),
        "noticeDifference": snap.get("noticeDifference"),
        "calculatedDifference": snap.get("calculatedDifference"),
        "explainedAmount": snap.get("explainedAmount"),
        "unexplainedAmount": snap.get("unexplainedAmount"),
        "ruleVersion": snap.get("ruleVersion"),
        "findingCount": snap.get("findingCount"),
        "runId": snap.get("runId"),
    }


def compare_versions(draft_id: str, from_version: int, to_version: int) -> dict:
    versions = versions_mod.list_versions(draft_id)
    old = next((v for v in versions if v["version"] == from_version), None)
    new = next((v for v in versions if v["version"] == to_version), None)
    if old is None or new is None:
        raise LookupError(f"Versions {from_version}/{to_version} not found.")
    old_ids, new_ids = set(old["findingIds"]), set(new["findingIds"])
    old_ev, new_ev = set(old["evidenceIds"]), set(new["evidenceIds"])
    old_snap, new_snap = _snap_numbers(old["reconSnapshot"]), _snap_numbers(new["reconSnapshot"])
    snap_changed = {k for k in old_snap if old_snap.get(k) != new_snap.get(k)}
    structured = [
        {"field": "decision", "from": old["decision"], "to": new["decision"],
         "changed": old["decision"] != new["decision"], "kind": "Content change"},
        {"field": "findingReferences",
         "from": sorted(old_ids), "to": sorted(new_ids),
         "added": sorted(new_ids - old_ids), "removed": sorted(old_ids - new_ids),
         "changed": old_ids != new_ids, "kind": "Evidence / factual change"},
        {"field": "evidenceReferences",
         "from": sorted(old_ev), "to": sorted(new_ev),
         "added": sorted(new_ev - old_ev), "removed": sorted(old_ev - new_ev),
         "changed": old_ev != new_ev, "kind": "Evidence / factual change"},
        {"field": "ruleReference", "from": old["ruleVersion"], "to": new["ruleVersion"],
         "changed": old["ruleVersion"] != new["ruleVersion"], "kind": "Evidence / factual change"},
        {"field": "reconciliationSnapshot", "from": old_snap, "to": new_snap,
         "changedKeys": sorted(snap_changed), "changed": bool(snap_changed),
         "kind": "Evidence / factual change"},
        {"field": "reviewStatus", "from": old["reviewStatus"], "to": new["reviewStatus"],
         "changed": old["reviewStatus"] != new["reviewStatus"], "kind": "Content change"},
        {"field": "createdBy", "from": old["createdBy"], "to": new["createdBy"],
         "changed": old["createdBy"] != new["createdBy"], "kind": "Content change"},
    ]
    content_changes = _content_diff(old["content"], new["content"])
    return {
        "draftId": draft_id,
        "from": from_version,
        "to": to_version,
        "contentChanges": [
            {**c, "kind": f"Content change ({c['kind']})"} if c.get("kind") != "truncated" else c
            for c in content_changes
        ],
        "structuredChanges": structured,
        "hasChanges": bool(content_changes) or any(s["changed"] for s in structured),
    }


def export_compare_target(draft_id: str) -> None:
    if database.get_reply_draft(draft_id) is None:
        raise KeyError(draft_id)
