"""Inbox domain helpers for Inbox-first ingest state tracking."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class InboxState(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    REVIEW = "review"
    ARCHIVED = "archived"
    INGESTED = "ingested"


class InboxInputType(str, Enum):
    DOCUMENT_FILE = "document_file"
    MARKDOWN_FILE = "markdown_file"
    PASTED_TEXT = "pasted_text"


@dataclass(frozen=True)
class InboxItem:
    id: int
    source_id: int | None
    input_type: str
    state: str
    relpath: str | None
    content_hash: str | None
    title: str | None
    error_message: str | None
    lock_token: str | None
    locked_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class InboxEvent:
    id: int
    inbox_item_id: int
    seq: int
    event_type: str
    from_state: str | None
    to_state: str | None
    relpath: str | None
    message: str | None
    data: dict[str, Any]
    created_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _enum_value(value: InboxState | InboxInputType | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    return value


def _coerce_item(row: sqlite3.Row | tuple[Any, ...] | None, columns: list[str] | None = None) -> InboxItem | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        data = dict(row)
    else:
        assert columns is not None
        data = dict(zip(columns, row, strict=False))
    return InboxItem(**data)


def _coerce_event(row: sqlite3.Row | tuple[Any, ...] | None, columns: list[str] | None = None) -> InboxEvent | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        data = dict(row)
    else:
        assert columns is not None
        data = dict(zip(columns, row, strict=False))
    data["data"] = json.loads(data["data"] or "{}")
    return InboxEvent(**data)


def create_inbox_item(
    conn: sqlite3.Connection,
    *,
    input_type: InboxInputType | str,
    state: InboxState | str = InboxState.PENDING,
    source_id: int | None = None,
    relpath: str | None = None,
    content_hash: str | None = None,
    title: str | None = None,
    error_message: str | None = None,
    lock_token: str | None = None,
    locked_at: str | None = None,
    created_at: str | None = None,
) -> int:
    now = created_at or _now_iso()
    cur = conn.execute(
        """
        INSERT INTO inbox_items (
            source_id, input_type, state, relpath, content_hash, title,
            error_message, lock_token, locked_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            _enum_value(input_type),
            _enum_value(state),
            relpath,
            content_hash,
            title,
            error_message,
            lock_token,
            locked_at,
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def get_inbox_item(conn: sqlite3.Connection, item_id: int) -> InboxItem | None:
    cur = conn.execute(
        """
        SELECT id, source_id, input_type, state, relpath, content_hash, title,
               error_message, lock_token, locked_at, created_at, updated_at
        FROM inbox_items
        WHERE id = ?
        """,
        (item_id,),
    )
    row = cur.fetchone()
    columns = [col[0] for col in cur.description] if cur.description else None
    return _coerce_item(row, columns)


def list_inbox_items(conn: sqlite3.Connection, *, state: InboxState | str | None = None) -> list[InboxItem]:
    if state is None:
        cur = conn.execute(
            """
            SELECT id, source_id, input_type, state, relpath, content_hash, title,
                   error_message, lock_token, locked_at, created_at, updated_at
            FROM inbox_items
            ORDER BY id
            """
        )
    else:
        cur = conn.execute(
            """
            SELECT id, source_id, input_type, state, relpath, content_hash, title,
                   error_message, lock_token, locked_at, created_at, updated_at
            FROM inbox_items
            WHERE state = ?
            ORDER BY id
            """,
            (_enum_value(state),),
        )
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description] if cur.description else []
    return [_coerce_item(row, columns) for row in rows if row is not None]


def append_inbox_event(
    conn: sqlite3.Connection,
    *,
    inbox_item_id: int,
    event_type: str,
    from_state: InboxState | str | None = None,
    to_state: InboxState | str | None = None,
    relpath: str | None = None,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> int:
    now = created_at or _now_iso()
    next_seq = (
        conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM inbox_events WHERE inbox_item_id = ?",
            (inbox_item_id,),
        ).fetchone()[0]
    )
    cur = conn.execute(
        """
        INSERT INTO inbox_events (
            inbox_item_id, seq, event_type, from_state, to_state,
            relpath, message, data, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            inbox_item_id,
            next_seq,
            event_type,
            _enum_value(from_state),
            _enum_value(to_state),
            relpath,
            message,
            json.dumps(data or {}, sort_keys=True),
            now,
        ),
    )
    return int(cur.lastrowid)


def list_inbox_events(conn: sqlite3.Connection, inbox_item_id: int) -> list[InboxEvent]:
    cur = conn.execute(
        """
        SELECT id, inbox_item_id, seq, event_type, from_state, to_state,
               relpath, message, data, created_at
        FROM inbox_events
        WHERE inbox_item_id = ?
        ORDER BY seq
        """,
        (inbox_item_id,),
    )
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description] if cur.description else []
    return [_coerce_event(row, columns) for row in rows if row is not None]


def transition_inbox_item(
    conn: sqlite3.Connection,
    *,
    inbox_item_id: int,
    to_state: InboxState | str,
    event_type: str = "state_changed",
    relpath: str | None = None,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    error_message: str | None = None,
    lock_token: str | None = None,
    locked_at: str | None = None,
    created_at: str | None = None,
) -> InboxItem:
    item = get_inbox_item(conn, inbox_item_id)
    if item is None:
        raise ValueError(f"Inbox item not found: {inbox_item_id}")
    now = created_at or _now_iso()
    conn.execute(
        """
        UPDATE inbox_items
        SET state = ?,
            relpath = COALESCE(?, relpath),
            error_message = ?,
            lock_token = ?,
            locked_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            _enum_value(to_state),
            relpath,
            error_message,
            lock_token,
            locked_at,
            now,
            inbox_item_id,
        ),
    )
    append_inbox_event(
        conn,
        inbox_item_id=inbox_item_id,
        event_type=event_type,
        from_state=item.state,
        to_state=to_state,
        relpath=relpath or item.relpath,
        message=message,
        data=data,
        created_at=now,
    )
    updated = get_inbox_item(conn, inbox_item_id)
    assert updated is not None
    return updated
