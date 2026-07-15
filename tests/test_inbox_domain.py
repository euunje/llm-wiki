from __future__ import annotations

import sqlite3

from llm_wiki import config as cfg
from llm_wiki import db
from llm_wiki.inbox import InboxInputType, InboxState, create_inbox_item, list_inbox_events, transition_inbox_item
from llm_wiki.scaffold import scaffold


def test_init_db_migration_is_idempotent_and_preserves_existing_rows(tmp_path):
    db_path = tmp_path / ".wiki" / "state.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
            INSERT INTO schema_version (version) VALUES (3);
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relpath TEXT NOT NULL UNIQUE,
                content_hash TEXT NOT NULL,
                file_type TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                last_ingested TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE ingest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                source_id INTEGER,
                mode TEXT NOT NULL,
                pages_created INTEGER DEFAULT 0,
                pages_updated INTEGER DEFAULT 0,
                error TEXT
            );
            INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status)
            VALUES ('raw/seed.pdf', 'abc123', 'pdf', 99, '2026-07-15T00:00:00+00:00', 'pending');
            INSERT INTO ingest_runs (started_at, source_id, mode, pages_created, pages_updated)
            VALUES ('2026-07-15T00:10:00+00:00', 1, 'batch', 1, 0);
            """
        )
        conn.commit()

    db.init_db(db_path)
    db.init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == db.SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
        assert conn.execute("SELECT relpath, content_hash FROM sources WHERE id = 1").fetchone() == (
            "raw/seed.pdf",
            "abc123",
        )
        assert conn.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0] == 1
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'inbox_items'"
        ).fetchone() is not None
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'inbox_events'"
        ).fetchone() is not None


def test_inbox_states_and_helpers_follow_phase1_contract(tmp_path):
    db_path = tmp_path / ".wiki" / "state.sqlite"
    db.init_db(db_path)

    assert [state.value for state in InboxState] == [
        "pending",
        "processing",
        "failed",
        "review",
        "archived",
        "ingested",
    ]
    assert [kind.value for kind in InboxInputType] == [
        "document_file",
        "markdown_file",
        "pasted_text",
    ]

    with db.connect(db_path) as conn:
        item_id = create_inbox_item(
            conn,
            input_type=InboxInputType.DOCUMENT_FILE,
            relpath="Inbox/Files/spec.pdf",
            title="Spec",
        )
        item = transition_inbox_item(
            conn,
            inbox_item_id=item_id,
            to_state=InboxState.REVIEW,
            relpath="Inbox/_Review/spec.pdf",
            event_type="routed_to_review",
            message="Needs review",
            data={"reason": "ambiguous match"},
        )
        events = list_inbox_events(conn, item_id)

    assert item.state == InboxState.REVIEW.value
    assert item.relpath == "Inbox/_Review/spec.pdf"
    assert len(events) == 1
    assert events[0].seq == 1
    assert events[0].from_state == InboxState.PENDING.value
    assert events[0].to_state == InboxState.REVIEW.value
    assert events[0].data == {"reason": "ambiguous match"}


def test_wikipaths_exposes_inbox_path_semantics_and_respects_non_categories(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = cfg.WikiPaths(tmp_path)

    assert paths.inbox == (tmp_path / "Inbox").resolve()
    assert paths.inbox_files == (tmp_path / "Inbox" / "Files").resolve()
    assert paths.inbox_markdown == (tmp_path / "Inbox" / "Markdown").resolve()
    assert paths.inbox_text == (tmp_path / "Inbox" / "Text").resolve()
    assert paths.inbox_failed == (tmp_path / "Inbox" / "_Failed").resolve()
    assert paths.inbox_review == (tmp_path / "Inbox" / "_Review").resolve()
    assert paths.raw_archive == paths.raw

    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / ".wiki" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
paths:
  internal_dir: runtime
  wiki_dir: 20. Wiki
  page_dirs:
    non_categories: 00. Inbox/_Review
""".strip(),
        encoding="utf-8",
    )

    ja_paths = cfg.WikiPaths(tmp_path)
    assert ja_paths.non_categories == (tmp_path / "00. Inbox" / "_Review").resolve()
    assert ja_paths.inbox == (tmp_path / "00. Inbox").resolve()
    assert ja_paths.inbox_review == ja_paths.non_categories
    assert ja_paths.inbox_failed == (tmp_path / "00. Inbox" / "_Failed").resolve()
    assert ja_paths.inbox_files == (tmp_path / "00. Inbox" / "Files").resolve()
    assert not (ja_paths.inbox / "_Processing").exists()


def test_scaffold_creates_inbox_dirs_but_not_processing(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)

    assert paths.inbox.exists()
    assert paths.inbox_files.exists()
    assert paths.inbox_markdown.exists()
    assert paths.inbox_text.exists()
    assert paths.inbox_failed.exists()
    assert paths.inbox_review.exists()
    assert not (paths.inbox / "_Processing").exists()
