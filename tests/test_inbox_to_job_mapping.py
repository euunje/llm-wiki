from __future__ import annotations

from fastapi.testclient import TestClient

from llm_wiki import db, inbox, jobs
from llm_wiki.ingest_llm import IngestResult
from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app
from llm_wiki.webapp.routes import ingest as ingest_route


class _FakeManager:
    def __init__(self, paths):
        self.paths = paths

    def enqueue(self, source_id: int) -> int:
        return jobs.create_job(self.paths, source_id)


def _client_with_fake_manager(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    monkeypatch.setattr(ingest_route.jobs_module, "get_manager", lambda _: _FakeManager(paths))
    return paths, TestClient(create_app(paths))


def test_ingest_start_materializes_source_from_inbox_item_and_creates_job(tmp_path, monkeypatch):
    paths, client = _client_with_fake_manager(tmp_path, monkeypatch)

    upload = client.post(
        "/ingest/upload",
        files=[("files", ("dispatch-me.md", b"# Dispatch Me\n\nInbox to job mapping.", "text/markdown"))],
    )
    assert upload.status_code == 200
    inbox_item_id = upload.json()["files"][0]["inbox_item_id"]

    start = client.post("/ingest/start", data={"inbox_item_id": str(inbox_item_id)})

    assert start.status_code == 200
    payload = start.json()
    assert payload["ok"] is True
    assert payload["inbox_item_id"] == inbox_item_id
    assert payload["source_id"] > 0
    assert payload["job_id"] > 0

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, inbox_item_id)
        source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        source_relpath = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (payload["source_id"],)
        ).fetchone()[0]
        job_source_id = conn.execute(
            "SELECT source_id FROM ingest_jobs WHERE id = ?", (payload["job_id"],)
        ).fetchone()[0]

    assert item is not None
    assert item.source_id == payload["source_id"]
    assert source_count == 1
    assert source_relpath == "Inbox/Markdown/dispatch-me.md"
    assert job_source_id == payload["source_id"]


def test_ingest_scan_imports_raw_sources_into_inbox_without_creating_sources_rows(tmp_path, monkeypatch):
    paths, client = _client_with_fake_manager(tmp_path, monkeypatch)
    raw_file = paths.raw / "Imports" / "from-raw.md"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("# Imported\n\nRaw Sources should import into Inbox first.", encoding="utf-8")

    response = client.post("/ingest/scan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["registered"] == 1
    assert payload["counts"]["deduped"] == 0
    assert payload["counts"]["skipped"] == 0
    assert payload["counts"]["errors"] == 0
    assert payload["pending_count"] == 1
    assert payload["results"][0]["result"] == "registered"
    assert payload["results"][0]["relpath"] == "Inbox/Markdown/from-raw.md"
    assert payload["results"][0]["inbox_item_id"] > 0

    with db.connect(paths.state_db) as conn:
        pending_items = inbox.list_inbox_items(conn, state=inbox.InboxState.PENDING)
        source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

    assert len(pending_items) == 1
    assert pending_items[0].relpath == "Inbox/Markdown/from-raw.md"
    assert source_count == 0
    assert not raw_file.exists()
    assert (paths.inbox_markdown / "from-raw.md").exists()


def test_repeated_ingest_start_reuses_existing_source_id(tmp_path, monkeypatch):
    paths, client = _client_with_fake_manager(tmp_path, monkeypatch)
    upload = client.post(
        "/ingest/upload",
        files=[("files", ("reuse.txt", b"Reuse title\n\nSame inbox item started twice.", "text/plain"))],
    )
    assert upload.status_code == 200
    inbox_item_id = upload.json()["files"][0]["inbox_item_id"]

    first = client.post("/ingest/start", data={"inbox_item_id": str(inbox_item_id)})
    second = client.post("/ingest/start", data={"inbox_item_id": str(inbox_item_id)})

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert second_payload["source_id"] == first_payload["source_id"]

    with db.connect(paths.state_db) as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        job_count = conn.execute("SELECT COUNT(*) FROM ingest_jobs").fetchone()[0]
        item = inbox.get_inbox_item(conn, inbox_item_id)

    assert source_count == 1
    assert job_count == 2
    assert item is not None
    assert item.source_id == first_payload["source_id"]


def test_jobs_list_and_api_expose_linked_inbox_item_id(tmp_path, monkeypatch):
    paths, client = _client_with_fake_manager(tmp_path, monkeypatch)

    upload = client.post(
        "/ingest/upload",
        files=[("files", ("jobs-linked.md", b"# Linked job\n\nInbox metadata should be visible.", "text/markdown"))],
    )
    assert upload.status_code == 200
    inbox_item_id = upload.json()["files"][0]["inbox_item_id"]

    start = client.post("/ingest/start", data={"inbox_item_id": str(inbox_item_id)})
    assert start.status_code == 200
    job_id = start.json()["job_id"]

    job = jobs.get_job(paths, job_id)
    assert job is not None
    assert job.inbox_item_id == inbox_item_id

    listed_jobs = jobs.list_jobs(paths, limit=10)
    assert listed_jobs
    assert listed_jobs[0].inbox_item_id == inbox_item_id

    api_response = client.get("/api/jobs")
    assert api_response.status_code == 200
    api_jobs = api_response.json()["jobs"]
    assert api_jobs[0]["id"] == job_id
    assert api_jobs[0]["inbox_item_id"] == inbox_item_id


def test_jobs_list_preserves_null_inbox_item_id_for_legacy_jobs(tmp_path, monkeypatch):
    paths, _client = _client_with_fake_manager(tmp_path, monkeypatch)

    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("10. Raw Sources/legacy.md", "legacy-hash", "md", 42, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_jobs (source_id, state, created_at) VALUES (?, 'queued', ?)",
            (source_id, "2026-01-01T00:00:00+00:00"),
        )
        job_id = conn.execute("SELECT id FROM ingest_jobs").fetchone()[0]
        conn.commit()

    job = jobs.get_job(paths, job_id)
    assert job is not None
    assert job.inbox_item_id is None


def test_background_job_success_finalizes_linked_inbox_item_into_raw_archive(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    source_file = paths.root / "fixtures" / "job-finalize.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# Job Finalize\n\nBackground ingest archive move.\n", encoding="utf-8")
    registration = inbox.register_markdown_file(paths, source_file)
    materialized = inbox.materialize_source_for_inbox_item(paths, registration.item.id)
    job_id = jobs.create_job(paths, materialized.source_id)

    class FakeClient:
        provider = "test"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_ready(self):
            return None

        def close(self):
            return None

    def fake_ingest_source(paths_arg, source_id, client, callbacks, *, mode="interactive", thinking_for_extraction=True):
        result = IngestResult(
            source_id=source_id,
            source_title="Inbox/Markdown/job-finalize.md",
            source_slug="job-finalize",
            pages_created=2,
            pages_updated=0,
        )
        callbacks.on_complete(result)
        return result

    monkeypatch.setattr(jobs, "OllamaClient", FakeClient)
    monkeypatch.setattr(jobs.ingest_llm, "ingest_source", fake_ingest_source)

    manager = jobs.JobManager(paths, max_concurrent=1)
    manager._run_job(job_id)

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)
        source_relpath = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (materialized.source_id,)
        ).fetchone()[0]
        event_types = [event.event_type for event in inbox.list_inbox_events(conn, registration.item.id)]

    assert item is not None
    assert item.state == inbox.InboxState.INGESTED.value
    assert item.relpath == "raw/job-finalize.md"
    assert source_relpath == "raw/job-finalize.md"
    assert event_types[-2:] == ["moved_to_archive", "job_ingest_completed"]
    assert not (paths.inbox_markdown / "job-finalize.md").exists()
    assert (paths.raw_archive / "job-finalize.md").exists()


def test_ingest_page_does_not_show_legacy_error_when_inbox_item_linked(tmp_path, monkeypatch):
    """When a source has 'error' status but a linked inbox item is still 'pending',
    the /ingest page must show only the inbox item (not a duplicate legacy entry)."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db
    from llm_wiki.webapp.main import create_app

    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        # Create a source with 'error' status (simulating failed ingest)
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Inbox/Markdown/dup-test.md",
                "hash-dup-test",
                "md",
                100,
                "2026-01-01T00:00:00+00:00",
                "error",
            ),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        # Create a linked inbox item still in 'pending' state
        conn.execute(
            "INSERT INTO inbox_items (source_id, input_type, state, relpath, content_hash, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                inbox.InboxInputType.MARKDOWN_FILE.value,
                inbox.InboxState.PENDING.value,
                "Inbox/Markdown/dup-test.md",
                "hash-dup-test",
                "Dup Test",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        inbox_item_id = conn.execute("SELECT id FROM inbox_items").fetchone()[0]
        conn.commit()

    client = TestClient(create_app(paths))
    response = client.get("/ingest")

    assert response.status_code == 200
    # The inbox item should appear
    assert "dup-test.md" in response.text
    # The legacy error source should NOT appear as a separate duplicate entry
    # Count occurrences of the filename - should only appear once (from inbox item)
    assert response.text.count("dup-test.md") == 1
    # The source should not appear as a legacy retry entry (no "재시도 필요" badge for this file)
    # Because it's managed by inbox, not legacy


def test_ingest_page_shows_legacy_error_when_no_inbox_item_linked(tmp_path, monkeypatch):
    """Legacy error sources must remain visible when they have no linked inbox item."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db
    from llm_wiki.webapp.main import create_app

    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        # Create a source with 'error' status and NO linked inbox item
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "10. Raw Sources/legacy-only.md",
                "hash-legacy-only",
                "md",
                100,
                "2026-01-01T00:00:00+00:00",
                "error",
            ),
        )
        conn.commit()

    client = TestClient(create_app(paths))
    response = client.get("/ingest")

    assert response.status_code == 200
    # The legacy error source should appear
    assert "legacy-only.md" in response.text
    assert "재시도 필요" in response.text


def test_background_job_failure_moves_linked_inbox_item_to_failed(tmp_path, monkeypatch):
    """When a background job fails, the linked inbox item must be marked as failed."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    source_file = paths.root / "fixtures" / "job-fail.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# Job Fail\n\nBackground ingest failure.\n", encoding="utf-8")
    registration = inbox.register_markdown_file(paths, source_file)
    materialized = inbox.materialize_source_for_inbox_item(paths, registration.item.id)
    job_id = jobs.create_job(paths, materialized.source_id)

    class FakeClient:
        provider = "test"

        def __init__(self, *args, **kwargs):
            pass

        def ensure_ready(self):
            return None

        def close(self):
            return None

    def fake_ingest_source_failure(
        paths_arg, source_id, client, callbacks, *, mode="interactive", thinking_for_extraction=True
    ):
        # Simulate a failed ingest (result.ok is computed from error/skipped)
        callbacks.on_error("Extraction failed: simulated error")
        return IngestResult(
            source_id=source_id,
            source_title="Job Fail",
            source_slug="job-fail",
            pages_created=0,
            pages_updated=0,
            error="Extraction failed: simulated error",
        )

    monkeypatch.setattr(jobs, "OllamaClient", FakeClient)
    monkeypatch.setattr(jobs.ingest_llm, "ingest_source", fake_ingest_source_failure)

    manager = jobs.JobManager(paths, max_concurrent=1)
    manager._run_job(job_id)

    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)
        job = jobs.get_job(paths, job_id)
        event_types = [event.event_type for event in inbox.list_inbox_events(conn, registration.item.id)]

    assert item is not None
    assert item.state == inbox.InboxState.FAILED.value
    assert job is not None
    assert job.state == "failed"
    assert "moved_to_failed" in event_types
