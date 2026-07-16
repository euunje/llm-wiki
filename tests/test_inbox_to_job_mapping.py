from __future__ import annotations

from fastapi.testclient import TestClient

from llm_wiki import db, inbox, jobs
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
