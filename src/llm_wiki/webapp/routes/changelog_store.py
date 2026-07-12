"""Changelog backing store — operational / config / playbook change history.

The backing store lives under the wiki's internal runtime directory
(e.g. ~/.wiki/changelog/change_history.json) so it stays outside the vault
and never mixes with source-of-truth wiki content.

Change history fields (minimum set from LLM-WIKI_MIGRATION_PLAN.md):
    change_id       — unique string ID (UUID)
    changed_at      — ISO-8601 timestamp
    changed_by      — author / actor
    change_type     — config | prompt | playbook | path_mapping | schema
    before_state    — JSON-serialisable snapshot before change
    after_state     — JSON-serialisable snapshot after change
    reason          — human-readable rationale
    source_file     — file or route that triggered the change
    affected_service — which llm-wiki component is affected
    rollback_available — bool
    verification_evidence — str | null
    linked_wiki_pages — list[str]
    status          — pending | applied | rolled_back | verified
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ... import config as cfg


class ChangeType(str, Enum):
    CONFIG = "config"
    PROMPT = "prompt"
    PLAYBOOK = "playbook"
    PATH_MAPPING = "path_mapping"
    SCHEMA = "schema"


class ChangeStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    VERIFIED = "verified"


def _store_file(paths: cfg.WikiPaths) -> Path:
    """Return the absolute path to the change_history.json store.

    Stored under the wiki's internal directory (never inside the vault)
    so runtime state stays separate from wiki content.
    """
    store_dir = paths.internal / "changelog"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir / "change_history.json"


def _load_store(paths: cfg.WikiPaths) -> list[dict[str, Any]]:
    """Load the change history list from disk, returning an empty list if absent."""
    store_path = _store_file(paths)
    if not store_path.exists():
        return []
    try:
        with store_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_store(paths: cfg.WikiPaths, entries: list[dict[str, Any]]) -> None:
    """Write the change history list to disk atomically."""
    store_path = _store_file(paths)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = store_path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        tmp.replace(store_path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def list_changes(
    paths: cfg.WikiPaths,
    limit: int = 100,
    change_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Return change history entries, newest first, optionally filtered."""
    entries = _load_store(paths)
    if change_type:
        entries = [e for e in entries if e.get("change_type") == change_type]
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return sorted(entries, key=lambda e: e.get("changed_at", ""), reverse=True)[:limit]


def create_change(
    paths: cfg.WikiPaths,
    changed_by: str,
    change_type: str,
    before_state: Any,
    after_state: Any,
    reason: str,
    source_file: str = "",
    affected_service: str = "",
    rollback_available: bool = False,
    verification_evidence: str | None = None,
    linked_wiki_pages: list[str] | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    """Create and persist a new change history entry. Returns the created entry."""
    entry: dict[str, Any] = {
        "change_id": str(uuid.uuid4()),
        "changed_at": datetime.now(timezone.utc).isoformat(),
        "changed_by": changed_by,
        "change_type": change_type,
        "before_state": before_state,
        "after_state": after_state,
        "reason": reason,
        "source_file": source_file,
        "affected_service": affected_service,
        "rollback_available": rollback_available,
        "verification_evidence": verification_evidence,
        "linked_wiki_pages": linked_wiki_pages or [],
        "status": status,
    }
    entries = _load_store(paths)
    entries.append(entry)
    _save_store(paths, entries)
    return entry


def get_change(paths: cfg.WikiPaths, change_id: str) -> dict[str, Any] | None:
    """Return a single change entry by id, or None if not found."""
    entries = _load_store(paths)
    for entry in entries:
        if entry.get("change_id") == change_id:
            return entry
    return None


def update_change_status(
    paths: cfg.WikiPaths,
    change_id: str,
    new_status: str,
    verification_evidence: str | None = None,
) -> dict[str, Any] | None:
    """Update the status (and optionally verification_evidence) of a change entry.

    Returns the updated entry, or None if change_id not found.
    """
    entries = _load_store(paths)
    for entry in entries:
        if entry.get("change_id") == change_id:
            entry["status"] = new_status
            if verification_evidence is not None:
                entry["verification_evidence"] = verification_evidence
            _save_store(paths, entries)
            return entry
    return None
