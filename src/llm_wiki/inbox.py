"""Inbox domain helpers for Inbox-first ingest state tracking."""

from __future__ import annotations

import json
import sqlite3
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from . import config as cfg
from . import db, parsers
from .page_writer import ParsedPage
from .parsers.base import fallback_title_from_path


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


@dataclass(frozen=True)
class InboxRegistrationResult:
    item: InboxItem
    stored_path: Path
    deduped: bool = False


@dataclass(frozen=True)
class InboxMoveResult:
    item: InboxItem
    source_path: Path
    target_path: Path | None
    report_path: Path | None = None
    moved: bool = True


@dataclass(frozen=True)
class InboxSourceMaterializationResult:
    item: InboxItem
    source_id: int
    created: bool
    reused: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_inbox_dirs(paths: cfg.WikiPaths) -> None:
    for directory in (
        paths.inbox,
        paths.inbox_files,
        paths.inbox_markdown,
        paths.inbox_text,
        paths.inbox_failed,
        paths.inbox_review,
        paths.raw_archive,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _unique_destination(dest_dir: Path, filename: str) -> Path:
    target = dest_dir / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _slugify_filename(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed or "pasted-text"


def _try_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _safe_copy_or_move(source_path: Path, dest_path: Path, *, copy: bool) -> Path:
    # Guard: same-path short-circuit must verify source exists to avoid silent
    # success when move_to_pending is called on a pending item whose file is
    # missing but whose relpath resolves to the same path as the destination.
    if source_path.resolve() == dest_path.resolve():
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        return dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    if copy:
        return dest_path
    try:
        source_path.unlink()
    except OSError:
        try:
            dest_path.unlink()
        except OSError:
            pass
        raise
    return dest_path


def _read_registered_metadata(path: Path) -> tuple[str | None, str | None]:
    try:
        parsed = parsers.parse(path)
        return parsed.title, parsed.content_hash
    except parsers.ParserError:
        return fallback_title_from_path(path), None


def _update_inbox_item_source_link(
    conn: sqlite3.Connection,
    *,
    inbox_item_id: int,
    source_id: int,
    content_hash: str | None,
    title: str | None,
) -> InboxItem:
    now = _now_iso()
    conn.execute(
        """
        UPDATE inbox_items
        SET source_id = ?,
            content_hash = COALESCE(?, content_hash),
            title = COALESCE(?, title),
            updated_at = ?
        WHERE id = ?
        """,
        (source_id, content_hash, title, now, inbox_item_id),
    )
    item = get_inbox_item(conn, inbox_item_id)
    assert item is not None
    return item


def _refresh_existing_source_row(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    relpath: str,
    content_hash: str,
    file_type: str,
    byte_count: int,
) -> None:
    conn.execute(
        """
        UPDATE sources
        SET relpath = ?,
            content_hash = ?,
            file_type = ?,
            bytes = ?,
            status = 'pending',
            last_ingested = NULL
        WHERE id = ?
        """,
        (relpath, content_hash, file_type, byte_count, source_id),
    )


def _find_existing_inbox_item_by_hash(
    conn: sqlite3.Connection, content_hash: str | None
) -> InboxItem | None:
    if not content_hash:
        return None
    cur = conn.execute(
        """
        SELECT id, source_id, input_type, state, relpath, content_hash, title,
               error_message, lock_token, locked_at, created_at, updated_at
        FROM inbox_items
        WHERE content_hash = ?
        ORDER BY id
        LIMIT 1
        """,
        (content_hash,),
    )
    row = cur.fetchone()
    columns = [col[0] for col in cur.description] if cur.description else None
    return _coerce_item(row, columns)


def _item_stored_path(paths: cfg.WikiPaths, item: InboxItem) -> Path | None:
    if not item.relpath:
        return None
    return (paths.root / item.relpath).resolve()


def _sanitize_error_detail(error: str | BaseException) -> str:
    message = str(error).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in message.split("\n") if line.strip()]
    sanitized = " | ".join(lines)
    return sanitized[:1000]


def _create_report_text(
    *,
    item: InboxItem,
    failed_relpath: str,
    error: str | BaseException,
    phase: str | None,
    retry_hint: str | None,
) -> str:
    error_type = error.__class__.__name__ if isinstance(error, BaseException) else "Error"
    lines = [
        "# Inbox Failure Diagnostic",
        "",
        f"- inbox_item_id: {item.id}",
        f"- phase: {phase or 'unknown'}",
        f"- state: {InboxState.FAILED.value}",
        f"- source_path: {failed_relpath}",
        f"- error_type: {error_type}",
        f"- error: {_sanitize_error_detail(error)}",
        f"- retry_hint: {retry_hint or 'Retry after addressing the failure cause.'}",
    ]
    return "\n".join(lines) + "\n"


def _register_file(
    paths: cfg.WikiPaths,
    *,
    source_path: Path,
    dest_dir: Path,
    input_type: InboxInputType,
    copy: bool,
    event_type: str,
) -> InboxRegistrationResult:
    _ensure_inbox_dirs(paths)
    source_path = source_path.expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"File not found: {source_path}")
    title, content_hash = _read_registered_metadata(source_path)
    with db.connect(paths.state_db) as conn:
        existing = _find_existing_inbox_item_by_hash(conn, content_hash)
        existing_path = _item_stored_path(paths, existing) if existing is not None else None
        if existing is not None and existing_path is not None:
            append_inbox_event(
                conn,
                inbox_item_id=existing.id,
                event_type="duplicate_content_hash_registered",
                from_state=existing.state,
                to_state=existing.state,
                relpath=existing.relpath,
                message=f"Duplicate {input_type.value} registration reused existing inbox item #{existing.id}",
                data={
                    "copy": copy,
                    "source_path": str(source_path),
                    "stored_path": str(existing_path),
                    "content_hash": content_hash,
                    "requested_input_type": input_type.value,
                    "db_state": existing.state,
                    "retryable": False,
                    "deduped": True,
                    "source_preserved": True,
                },
            )
            return InboxRegistrationResult(item=existing, stored_path=existing_path, deduped=True)
    dest_path = source_path if source_path.parent == dest_dir else _unique_destination(dest_dir, source_path.name)
    stored_path = _safe_copy_or_move(source_path, dest_path, copy=copy)
    relpath = _try_relpath(stored_path, paths.root)
    with db.connect(paths.state_db) as conn:
        item_id = create_inbox_item(
            conn,
            input_type=input_type,
            relpath=relpath,
            content_hash=content_hash,
            title=title,
        )
        append_inbox_event(
            conn,
            inbox_item_id=item_id,
            event_type=event_type,
            to_state=InboxState.PENDING,
            relpath=relpath,
            data={
                "copy": copy,
                "source_path": str(source_path),
                "stored_path": str(stored_path),
                "db_state": InboxState.PENDING.value,
                "retryable": False,
                "deduped": False,
            },
        )
        item = get_inbox_item(conn, item_id)
    assert item is not None
    return InboxRegistrationResult(item=item, stored_path=stored_path, deduped=False)


def _current_file_path(paths: cfg.WikiPaths, item: InboxItem) -> Path:
    if not item.relpath:
        raise ValueError(f"Inbox item has no relpath: {item.id}")
    return (paths.root / item.relpath).resolve()


def _move_item_file(
    paths: cfg.WikiPaths,
    *,
    inbox_item_id: int,
    dest_dir: Path,
    to_state: InboxState,
    event_type: str,
    failed_event_type: str,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> InboxMoveResult:
    _ensure_inbox_dirs(paths)
    with db.connect(paths.state_db) as conn:
        item = get_inbox_item(conn, inbox_item_id)
        if item is None:
            raise ValueError(f"Inbox item not found: {inbox_item_id}")
        source_path = _current_file_path(paths, item)
        target_path = _unique_destination(dest_dir, source_path.name)
        try:
            moved_path = _safe_copy_or_move(source_path, target_path, copy=False)
        except OSError as exc:
            append_inbox_event(
                conn,
                inbox_item_id=inbox_item_id,
                event_type=failed_event_type,
                from_state=item.state,
                to_state=item.state,
                relpath=item.relpath,
                message=f"Failed to move file: {exc}",
                data={
                    "source_path": str(source_path),
                    "target_path": str(target_path),
                    "db_state": item.state,
                    "retryable": True,
                },
            )
            updated = get_inbox_item(conn, inbox_item_id)
            assert updated is not None
            return InboxMoveResult(
                item=updated,
                source_path=source_path,
                target_path=target_path,
                moved=False,
            )
        relpath = _try_relpath(moved_path, paths.root)
        updated = transition_inbox_item(
            conn,
            inbox_item_id=inbox_item_id,
            to_state=to_state,
            event_type=event_type,
            relpath=relpath,
            message=message,
            data={
                "source_path": str(source_path),
                "target_path": str(moved_path),
                "db_state": to_state.value,
                "retryable": False,
                **(data or {}),
            },
            error_message=error_message,
            lock_token=None,
            locked_at=None,
        )
    return InboxMoveResult(item=updated, source_path=source_path, target_path=moved_path)


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


def materialize_source_for_inbox_item(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
) -> InboxSourceMaterializationResult:
    with db.connect(paths.state_db) as conn:
        item = get_inbox_item(conn, inbox_item_id)
        if item is None:
            raise ValueError(f"Inbox item not found: {inbox_item_id}")

        file_path = _current_file_path(paths, item)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Inbox item file not found: {file_path}")

        parsed = parsers.parse(file_path)
        relpath = item.relpath or _try_relpath(file_path, paths.root)

        if item.source_id is not None:
            existing_by_id = conn.execute(
                "SELECT id, relpath FROM sources WHERE id = ?",
                (item.source_id,),
            ).fetchone()
            if existing_by_id is not None and existing_by_id["relpath"] == relpath:
                _refresh_existing_source_row(
                    conn,
                    source_id=item.source_id,
                    relpath=relpath,
                    content_hash=parsed.content_hash,
                    file_type=parsed.file_type,
                    byte_count=parsed.bytes,
                )
                updated_item = _update_inbox_item_source_link(
                    conn,
                    inbox_item_id=inbox_item_id,
                    source_id=item.source_id,
                    content_hash=parsed.content_hash,
                    title=parsed.title,
                )
                append_inbox_event(
                    conn,
                    inbox_item_id=inbox_item_id,
                    event_type="source_materialized_reused",
                    from_state=updated_item.state,
                    to_state=updated_item.state,
                    relpath=relpath,
                    message=f"Reused linked source #{item.source_id}",
                    data={
                        "source_id": item.source_id,
                        "source_relpath": relpath,
                        "content_hash": parsed.content_hash,
                        "reused": True,
                        "created": False,
                    },
                )
                return InboxSourceMaterializationResult(
                    item=updated_item,
                    source_id=item.source_id,
                    created=False,
                    reused=True,
                )

        existing_by_relpath = conn.execute(
            "SELECT id FROM sources WHERE relpath = ?",
            (relpath,),
        ).fetchone()
        if existing_by_relpath is not None:
            source_id = int(existing_by_relpath["id"])
            _refresh_existing_source_row(
                conn,
                source_id=source_id,
                relpath=relpath,
                content_hash=parsed.content_hash,
                file_type=parsed.file_type,
                byte_count=parsed.bytes,
            )
            updated_item = _update_inbox_item_source_link(
                conn,
                inbox_item_id=inbox_item_id,
                source_id=source_id,
                content_hash=parsed.content_hash,
                title=parsed.title,
            )
            append_inbox_event(
                conn,
                inbox_item_id=inbox_item_id,
                event_type="source_materialized_reused",
                from_state=updated_item.state,
                to_state=updated_item.state,
                relpath=relpath,
                message=f"Reused existing source #{source_id} for {relpath}",
                data={
                    "source_id": source_id,
                    "source_relpath": relpath,
                    "content_hash": parsed.content_hash,
                    "reused": True,
                    "created": False,
                },
            )
            return InboxSourceMaterializationResult(
                item=updated_item,
                source_id=source_id,
                created=False,
                reused=True,
            )

        same_hash_other_source = conn.execute(
            "SELECT id, relpath FROM sources WHERE content_hash = ? ORDER BY id LIMIT 1",
            (parsed.content_hash,),
        ).fetchone()
        if same_hash_other_source is not None:
            append_inbox_event(
                conn,
                inbox_item_id=inbox_item_id,
                event_type="source_materialization_hash_conflict",
                from_state=item.state,
                to_state=item.state,
                relpath=relpath,
                message=(
                    f"Existing source #{same_hash_other_source['id']} has the same content hash "
                    f"but a different relpath; materializing a new source row for provenance"
                ),
                data={
                    "existing_source_id": int(same_hash_other_source["id"]),
                    "existing_relpath": same_hash_other_source["relpath"],
                    "requested_relpath": relpath,
                    "content_hash": parsed.content_hash,
                    "reused": False,
                },
            )

        cur = conn.execute(
            """
            INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (relpath, parsed.content_hash, parsed.file_type, parsed.bytes, _now_iso()),
        )
        source_id = int(cur.lastrowid)
        updated_item = _update_inbox_item_source_link(
            conn,
            inbox_item_id=inbox_item_id,
            source_id=source_id,
            content_hash=parsed.content_hash,
            title=parsed.title,
        )
        append_inbox_event(
            conn,
            inbox_item_id=inbox_item_id,
            event_type="source_materialized",
            from_state=updated_item.state,
            to_state=updated_item.state,
            relpath=relpath,
            message=f"Materialized source #{source_id} for inbox item #{inbox_item_id}",
            data={
                "source_id": source_id,
                "source_relpath": relpath,
                "content_hash": parsed.content_hash,
                "reused": False,
                "created": True,
            },
        )
        return InboxSourceMaterializationResult(
            item=updated_item,
            source_id=source_id,
            created=True,
            reused=False,
        )


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


def register_document_file(
    paths: cfg.WikiPaths,
    source_path: Path,
    *,
    copy: bool = True,
) -> InboxRegistrationResult:
    return _register_file(
        paths,
        source_path=source_path,
        dest_dir=paths.inbox_files,
        input_type=InboxInputType.DOCUMENT_FILE,
        copy=copy,
        event_type="registered_document_file",
    )


def register_markdown_file(
    paths: cfg.WikiPaths,
    source_path: Path,
    *,
    copy: bool = True,
) -> InboxRegistrationResult:
    return _register_file(
        paths,
        source_path=source_path,
        dest_dir=paths.inbox_markdown,
        input_type=InboxInputType.MARKDOWN_FILE,
        copy=copy,
        event_type="registered_markdown_file",
    )


def register_pasted_text(
    paths: cfg.WikiPaths,
    *,
    title: str,
    body: str,
    source_url: str | None = None,
    tags: list[str] | None = None,
) -> InboxRegistrationResult:
    _ensure_inbox_dirs(paths)
    created_at = _now_iso()
    frontmatter: dict[str, Any] = {
        "title": title,
        "input_type": InboxInputType.PASTED_TEXT.value,
        "created_at": created_at,
    }
    if source_url:
        frontmatter["source_url"] = source_url
    if tags:
        frontmatter["tags"] = tags
    filename = f"{_slugify_filename(title)}.md"
    stored_path = _unique_destination(paths.inbox_text, filename)
    content = ParsedPage(frontmatter=frontmatter, body=body).to_markdown()
    stored_path.write_text(content, encoding="utf-8")
    title_value, content_hash = _read_registered_metadata(stored_path)
    relpath = _try_relpath(stored_path, paths.root)
    with db.connect(paths.state_db) as conn:
        item_id = create_inbox_item(
            conn,
            input_type=InboxInputType.PASTED_TEXT,
            relpath=relpath,
            content_hash=content_hash,
            title=title_value,
            created_at=created_at,
        )
        append_inbox_event(
            conn,
            inbox_item_id=item_id,
            event_type="registered_pasted_text",
            to_state=InboxState.PENDING,
            relpath=relpath,
            data={
                "source_path": str(stored_path),
                "target_path": str(stored_path),
                "db_state": InboxState.PENDING.value,
                "retryable": False,
                "source_url": source_url,
                "tags": tags or [],
            },
        )
        item = get_inbox_item(conn, item_id)
    assert item is not None
    return InboxRegistrationResult(item=item, stored_path=stored_path)


def register_uploaded_bytes(
    paths: cfg.WikiPaths,
    *,
    filename: str,
    content: bytes,
) -> InboxRegistrationResult:
    if not filename:
        raise ValueError("filename required")
    if not parsers.is_supported(Path(filename)):
        raise ValueError(f"Unsupported file type: {Path(filename).suffix or '(no extension)'}")
    _ensure_inbox_dirs(paths)
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".markdown"}:
        register = register_markdown_file
    else:
        register = register_document_file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / Path(filename).name
        temp_path.write_bytes(content)
        return register(paths, temp_path, copy=False)


def acquire_processing_lock(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
    *,
    lock_token: str,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> InboxItem:
    with db.connect(paths.state_db) as conn:
        item = transition_inbox_item(
            conn,
            inbox_item_id=inbox_item_id,
            to_state=InboxState.PROCESSING,
            event_type="processing_lock_acquired",
            message=message,
            data={"db_state": InboxState.PROCESSING.value, **(data or {})},
            lock_token=lock_token,
            locked_at=_now_iso(),
            error_message=None,
        )
    return item


def move_to_archive(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
    *,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> InboxMoveResult:
    return _move_item_file(
        paths,
        inbox_item_id=inbox_item_id,
        dest_dir=paths.raw_archive,
        to_state=InboxState.ARCHIVED,
        event_type="moved_to_archive",
        failed_event_type="archive_move_failed",
        message=message,
        data=data,
    )


def move_to_review(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
    *,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> InboxMoveResult:
    return _move_item_file(
        paths,
        inbox_item_id=inbox_item_id,
        dest_dir=paths.inbox_review,
        to_state=InboxState.REVIEW,
        event_type="moved_to_review",
        failed_event_type="review_move_failed",
        message=message,
        data=data,
    )


def move_to_pending(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
    *,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> InboxMoveResult:
    with db.connect(paths.state_db) as conn:
        item = get_inbox_item(conn, inbox_item_id)
    if item is None:
        raise ValueError(f"Inbox item not found: {inbox_item_id}")

    if item.input_type == InboxInputType.MARKDOWN_FILE.value:
        dest_dir = paths.inbox_markdown
    elif item.input_type == InboxInputType.PASTED_TEXT.value:
        dest_dir = paths.inbox_text
    else:
        dest_dir = paths.inbox_files

    return _move_item_file(
        paths,
        inbox_item_id=inbox_item_id,
        dest_dir=dest_dir,
        to_state=InboxState.PENDING,
        event_type="moved_to_pending",
        failed_event_type="pending_move_failed",
        message=message,
        data=data,
        error_message=None,
    )


def move_to_failed(
    paths: cfg.WikiPaths,
    inbox_item_id: int,
    *,
    error: str | BaseException,
    phase: str | None = None,
    message: str | None = None,
    retry_hint: str | None = None,
    data: dict[str, Any] | None = None,
) -> InboxMoveResult:
    move_result = _move_item_file(
        paths,
        inbox_item_id=inbox_item_id,
        dest_dir=paths.inbox_failed,
        to_state=InboxState.FAILED,
        event_type="moved_to_failed",
        failed_event_type="failed_move_failed",
        message=message,
        data={
            "phase": phase,
            "retry_hint": retry_hint,
            **(data or {}),
        },
        error_message=_sanitize_error_detail(error),
    )
    if not move_result.moved or move_result.target_path is None:
        return move_result
    report_name = f"{move_result.target_path.name}.diagnostic.md"
    report_path = _unique_destination(move_result.target_path.parent, report_name)
    report_text = _create_report_text(
        item=move_result.item,
        failed_relpath=move_result.item.relpath or str(move_result.target_path),
        error=error,
        phase=phase,
        retry_hint=retry_hint,
    )
    report_path.write_text(report_text, encoding="utf-8")
    with db.connect(paths.state_db) as conn:
        append_inbox_event(
            conn,
            inbox_item_id=inbox_item_id,
            event_type="failed_diagnostic_created",
            from_state=InboxState.FAILED,
            to_state=InboxState.FAILED,
            relpath=move_result.item.relpath,
            data={
                "report_path": str(report_path),
                "db_state": InboxState.FAILED.value,
                "retryable": True,
                "phase": phase,
            },
        )
    return InboxMoveResult(
        item=move_result.item,
        source_path=move_result.source_path,
        target_path=move_result.target_path,
        report_path=report_path,
        moved=True,
    )
