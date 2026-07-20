from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from llm_wiki.common import ensure_parent, utc_now


@dataclass
class SchemaResult:
    db_path: Path
    created: bool
    migrations_applied: list[str]
    fts5_enabled: bool
    fts5_message: str


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sources (
      id TEXT PRIMARY KEY,
      source_type TEXT NOT NULL,
      title TEXT NOT NULL,
      origin TEXT,
      raw_path TEXT,
      normalized_path TEXT,
      content_hash TEXT NOT NULL,
      pipeline_stage TEXT NOT NULL DEFAULT 'created',
      review_status TEXT NOT NULL DEFAULT 'pending',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash)",
    """
    CREATE TABLE IF NOT EXISTS source_chunks (
      id TEXT PRIMARY KEY,
      source_id TEXT NOT NULL REFERENCES sources(id),
      chunk_index INTEGER NOT NULL,
      text TEXT NOT NULL,
      token_count INTEGER NOT NULL,
      locator_json TEXT NOT NULL,
      embedding_status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(source_id, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
      id TEXT PRIMARY KEY,
      target_type TEXT NOT NULL,
      target_id TEXT NOT NULL,
      model TEXT NOT NULL,
      backend TEXT NOT NULL,
      dimension INTEGER NOT NULL,
      vector_blob BLOB,
      vector_json TEXT,
      index_status TEXT NOT NULL DEFAULT 'pending',
      generated_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(target_type, target_id, model)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      job_type TEXT NOT NULL,
      target_type TEXT,
      target_id TEXT,
      status TEXT NOT NULL DEFAULT 'queued',
      input_refs_json TEXT NOT NULL DEFAULT '[]',
      output_refs_json TEXT NOT NULL DEFAULT '[]',
      error_json TEXT,
      retry_count INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL,
      started_at TEXT,
      finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
      id TEXT PRIMARY KEY,
      job_id TEXT REFERENCES jobs(id),
      agent_type TEXT NOT NULL,
      provider TEXT,
      model TEXT,
      task_type TEXT NOT NULL,
      prompt_version_id TEXT,
      input_refs_json TEXT NOT NULL DEFAULT '[]',
      output_refs_json TEXT NOT NULL DEFAULT '[]',
      artifact_id TEXT,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      error_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
      id TEXT PRIMARY KEY,
      artifact_type TEXT NOT NULL,
      task_type TEXT,
      target_type TEXT,
      target_id TEXT,
      run_id TEXT,
      path TEXT NOT NULL,
      content_hash TEXT,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_candidates (
      id TEXT PRIMARY KEY,
      candidate_type TEXT NOT NULL,
      candidate_key TEXT NOT NULL,
      source_id TEXT,
      run_id TEXT REFERENCES agent_runs(id),
      payload_json TEXT NOT NULL,
      review_route TEXT NOT NULL,
      review_reason TEXT,
      related_candidate_keys_json TEXT NOT NULL DEFAULT '[]',
      status TEXT NOT NULL DEFAULT 'pending',
      superseded_by TEXT REFERENCES review_candidates(id),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS human_decisions (
      id TEXT PRIMARY KEY,
      candidate_id TEXT NOT NULL REFERENCES review_candidates(id),
      decision_type TEXT NOT NULL,
      decided_by TEXT NOT NULL,
      decided_at TEXT NOT NULL,
      note TEXT,
      retry_instruction_id TEXT,
      metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retry_instructions (
      id TEXT PRIMARY KEY,
      target_candidate_id TEXT NOT NULL REFERENCES review_candidates(id),
      reason TEXT NOT NULL,
      instruction TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      consumed_run_id TEXT REFERENCES agent_runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prompt_versions (
      id TEXT PRIMARY KEY,
      task_type TEXT NOT NULL,
      version_label TEXT NOT NULL,
      state TEXT NOT NULL,
      prompt_text TEXT NOT NULL,
      change_note TEXT,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      confirmed_at TEXT,
      bypass_test INTEGER NOT NULL DEFAULT 0,
      UNIQUE(task_type, version_label)
    )
    """,
    # FR-3-NO-05: migration adds bypass_test column to existing prompt_versions tables.
    "ALTER TABLE prompt_versions ADD COLUMN bypass_test INTEGER NOT NULL DEFAULT 0",
]


FTS_STATEMENTS = [
    "CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts USING fts5(chunk_id UNINDEXED, source_id UNINDEXED, text)",
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_ai AFTER INSERT ON source_chunks BEGIN
      INSERT INTO source_chunks_fts(rowid, chunk_id, source_id, text)
      VALUES (new.rowid, new.id, new.source_id, new.text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_ad AFTER DELETE ON source_chunks BEGIN
      INSERT INTO source_chunks_fts(source_chunks_fts, rowid, chunk_id, source_id, text)
      VALUES('delete', old.rowid, old.id, old.source_id, old.text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_au AFTER UPDATE OF text, source_id ON source_chunks BEGIN
      INSERT INTO source_chunks_fts(source_chunks_fts, rowid, chunk_id, source_id, text)
      VALUES('delete', old.rowid, old.id, old.source_id, old.text);
      INSERT INTO source_chunks_fts(rowid, chunk_id, source_id, text)
      VALUES (new.rowid, new.id, new.source_id, new.text);
    END
    """,
]


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_database(db_path: Path) -> SchemaResult:
    created = not db_path.exists()
    conn = connect(db_path)
    migrations_applied: list[str] = []
    try:
        for statement in SCHEMA_STATEMENTS:
            try:
                conn.execute(statement)
            except sqlite3.DatabaseError as exc:
                # ALTER TABLE on an already-migrated column will raise. Tolerate it
                # because the migration is recorded in schema_migrations below.
                if "duplicate column" not in str(exc).lower():
                    raise
        migration_id = "phase1_initial_schema"
        exists = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE id = ?", (migration_id,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (migration_id, utc_now()),
            )
            migrations_applied.append(migration_id)
        # FR-3-NO-05: record the bypass_test migration so it does not retry on existing DBs.
        bypass_migration = "phase3_prompt_bypass_test"
        bypass_exists = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE id = ?", (bypass_migration,)
        ).fetchone()
        if not bypass_exists:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(prompt_versions)").fetchall()]
            if "bypass_test" not in cols:
                conn.execute("ALTER TABLE prompt_versions ADD COLUMN bypass_test INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (bypass_migration, utc_now()),
            )
            migrations_applied.append(bypass_migration)
        fts5_enabled = True
        fts5_message = "FTS5 available"
        try:
            for statement in FTS_STATEMENTS:
                conn.execute(statement)
        except sqlite3.DatabaseError as exc:
            fts5_enabled = False
            fts5_message = f"FTS5 unavailable: {exc}"
        conn.commit()
        return SchemaResult(
            db_path=db_path,
            created=created,
            migrations_applied=migrations_applied,
            fts5_enabled=fts5_enabled,
            fts5_message=fts5_message,
        )
    finally:
        conn.close()


def inspect_database(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {"exists": False, "tables": [], "fts5": False}
    conn = connect(db_path)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
            ).fetchall()
        ]
        fts5 = "source_chunks_fts" in tables
        return {"exists": True, "tables": tables, "fts5": fts5}
    finally:
        conn.close()
