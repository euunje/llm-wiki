from __future__ import annotations

from typer.testing import CliRunner

from llm_wiki import db, inbox
from llm_wiki.cli import app
from llm_wiki.ingest_llm import IngestResult
from llm_wiki.scaffold import scaffold


runner = CliRunner()


def _env(paths) -> dict[str, str]:
    return {"WIKI_ROOT": str(paths.root)}


def _register_markdown(paths, name: str, content: str) -> inbox.InboxRegistrationResult:
    source = paths.root / "tmp-tests" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content, encoding="utf-8")
    return inbox.register_markdown_file(paths, source)


def test_status_shows_inbox_counts_and_review_hint(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)

    pending = _register_markdown(paths, "pending.md", "# Pending\n")
    processing = _register_markdown(paths, "processing.md", "# Processing\n")
    review = _register_markdown(paths, "review.md", "# Review\n")
    failed = _register_markdown(paths, "failed.md", "# Failed\n")

    inbox.acquire_processing_lock(paths, processing.item.id, lock_token="lock-1")
    inbox.move_to_review(paths, review.item.id, message="needs review")
    inbox.move_to_failed(paths, failed.item.id, error="boom", message="failed")
    inbox.materialize_source_for_inbox_item(paths, pending.item.id)

    result = runner.invoke(app, ["status"], env=_env(paths))

    assert result.exit_code == 0
    assert "Inbox" in result.output
    assert "Pending" in result.output and "1" in result.output
    assert "Processing" in result.output and "1" in result.output
    assert "Review" in result.output and "1" in result.output
    assert "Failed" in result.output and "1" in result.output
    assert "/inbox?state=review" in result.output


def test_retry_moves_failed_item_back_to_pending_and_cleans_diagnostic(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)

    registration = _register_markdown(paths, "retry-me.md", "# Retry Me\n")
    failed = inbox.move_to_failed(paths, registration.item.id, error="boom", message="failed")

    assert failed.report_path is not None and failed.report_path.exists()

    result = runner.invoke(app, ["retry", str(registration.item.id)], env=_env(paths))

    assert result.exit_code == 0
    assert f"Inbox item #{registration.item.id} moved back to pending." in result.output
    assert "Removed stale failure diagnostic report." in result.output

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)

    assert item is not None
    assert item.state == inbox.InboxState.PENDING.value
    assert item.relpath == "Inbox/Markdown/retry-me.md"
    assert not failed.report_path.exists()
    assert (paths.inbox_markdown / "retry-me.md").exists()


def test_ingest_processes_pending_inbox_items_via_materialization_path(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    registration = _register_markdown(paths, "ingest-me.md", "# Ingest Me\n\nInbox first.\n")
    called_source_ids: list[int] = []

    class FakeClient:
        provider = "test"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_ready(self):
            return None

        def close(self):
            return None

    def fake_ingest_source(paths_arg, source_id, client, callbacks, *, mode="interactive", thinking_for_extraction=True):
        called_source_ids.append(source_id)
        with db.connect(paths_arg.state_db) as conn:
            row = conn.execute(
                "SELECT relpath FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        source_title = row["relpath"] if row is not None else f"source-{source_id}"
        result = IngestResult(
            source_id=source_id,
            source_title=source_title,
            source_slug="ingest-me",
            pages_created=1,
            pages_updated=0,
        )
        callbacks.on_complete(result)
        return result

    monkeypatch.setattr("llm_wiki.cli.OllamaClient", FakeClient)
    monkeypatch.setattr("llm_wiki.cli.ingest_llm.ingest_source", fake_ingest_source)
    monkeypatch.setattr("llm_wiki.cli.search.is_available", lambda: False)

    result = runner.invoke(app, ["ingest", "--batch", "--no-discover"], env=_env(paths))

    assert result.exit_code == 0
    assert "LLM ready" in result.output
    assert "1 ingested" in result.output

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)
        source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        source_relpath = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (called_source_ids[0],)
        ).fetchone()[0]
        event_types = [event.event_type for event in inbox.list_inbox_events(conn, registration.item.id)]

    assert called_source_ids
    assert source_count == 1
    assert item is not None
    assert item.source_id == called_source_ids[0]
    assert item.state == inbox.InboxState.INGESTED.value
    assert item.relpath == "raw/ingest-me.md"
    assert source_relpath == "raw/ingest-me.md"
    assert event_types[-2:] == ["moved_to_archive", "cli_ingest_completed"]
    assert not (paths.inbox_markdown / "ingest-me.md").exists()
    assert (paths.raw_archive / "ingest-me.md").exists()


def test_ingest_source_id_without_linked_inbox_item_keeps_legacy_raw_source(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    raw_path = paths.raw_archive / "legacy-source.md"
    raw_path.write_text("# Legacy\n\nAlready in raw.\n", encoding="utf-8")

    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("raw/legacy-source.md", "legacy-hash", "md", raw_path.stat().st_size, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.commit()

    class FakeClient:
        provider = "test"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_ready(self):
            return None

        def close(self):
            return None

    def fake_ingest_source(paths_arg, source_id_arg, client, callbacks, *, mode="interactive", thinking_for_extraction=True):
        result = IngestResult(
            source_id=source_id_arg,
            source_title="raw/legacy-source.md",
            source_slug="legacy-source",
            pages_created=1,
            pages_updated=0,
        )
        callbacks.on_complete(result)
        return result

    monkeypatch.setattr("llm_wiki.cli.OllamaClient", FakeClient)
    monkeypatch.setattr("llm_wiki.cli.ingest_llm.ingest_source", fake_ingest_source)
    monkeypatch.setattr("llm_wiki.cli.search.is_available", lambda: False)

    result = runner.invoke(
        app,
        ["ingest", str(source_id), "--batch", "--no-discover"],
        env=_env(paths),
    )

    assert result.exit_code == 0
    assert raw_path.exists()
    with db.connect(paths.state_db) as conn:
        inbox_count = conn.execute("SELECT COUNT(*) FROM inbox_items").fetchone()[0]
        source_relpath = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (source_id,)
        ).fetchone()[0]

    assert inbox_count == 0
    assert source_relpath == "raw/legacy-source.md"


def test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    registration = _register_markdown(
        paths, "linked-ingest.md", "# Linked Ingest\n\nSource-id entry with linked item.\n"
    )
    materialized = inbox.materialize_source_for_inbox_item(paths, registration.item.id)
    called_source_ids: list[int] = []

    class FakeClient:
        provider = "test"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_ready(self):
            return None

        def close(self):
            return None

    def fake_ingest_source(paths_arg, source_id, client, callbacks, *, mode="interactive", thinking_for_extraction=True):
        called_source_ids.append(source_id)
        with db.connect(paths_arg.state_db) as conn:
            row = conn.execute(
                "SELECT relpath FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        source_title = row["relpath"] if row is not None else f"source-{source_id}"
        result = IngestResult(
            source_id=source_id,
            source_title=source_title,
            source_slug="linked-ingest",
            pages_created=1,
            pages_updated=0,
        )
        callbacks.on_complete(result)
        return result

    monkeypatch.setattr("llm_wiki.cli.OllamaClient", FakeClient)
    monkeypatch.setattr("llm_wiki.cli.ingest_llm.ingest_source", fake_ingest_source)
    monkeypatch.setattr("llm_wiki.cli.search.is_available", lambda: False)

    result = runner.invoke(
        app,
        ["ingest", str(materialized.source_id), "--batch", "--no-discover"],
        env=_env(paths),
    )

    assert result.exit_code == 0, result.output
    assert called_source_ids == [materialized.source_id]
    assert "1 ingested" in result.output

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)
        source_relpath = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (materialized.source_id,)
        ).fetchone()[0]
        event_types = [event.event_type for event in inbox.list_inbox_events(conn, registration.item.id)]

    assert item is not None
    assert item.source_id == materialized.source_id
    assert item.state == inbox.InboxState.INGESTED.value
    assert item.relpath == "raw/linked-ingest.md"
    assert source_relpath == "raw/linked-ingest.md"
    assert event_types[-2:] == ["moved_to_archive", "cli_ingest_completed"]
    assert not (paths.inbox_markdown / "linked-ingest.md").exists()
    assert (paths.raw_archive / "linked-ingest.md").exists()
