from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki import config as cfg
from llm_wiki import db, inbox
from llm_wiki.cli import _register_file_in_inbox
from llm_wiki.page_writer import parse_page
from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def _init_paths(tmp_path: Path) -> cfg.WikiPaths:
    paths = cfg.WikiPaths(tmp_path)
    db.init_db(paths.state_db)
    return paths


def test_document_registration_creates_file_in_inbox_files_and_inbox_item(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("Document title\n\nBody text for inbox registration.", encoding="utf-8")

    result = inbox.register_document_file(paths, source)

    assert result.stored_path == paths.inbox_files / "source.txt"
    assert result.stored_path.exists()
    assert source.exists()
    assert result.item.input_type == inbox.InboxInputType.DOCUMENT_FILE.value
    assert result.item.relpath == "Inbox/Files/source.txt"
    assert result.item.title == "Document title"


def test_markdown_registration_creates_file_in_inbox_markdown_and_preserves_content(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "notes.md"
    content = "---\ntitle: Preserved Title\ntags:\n  - inbox\n---\n\n# Heading\n\nMarkdown body.\n"
    source.write_text(content, encoding="utf-8")

    result = inbox.register_markdown_file(paths, source)

    assert result.stored_path == paths.inbox_markdown / "notes.md"
    assert result.stored_path.read_text(encoding="utf-8") == content
    assert result.item.input_type == inbox.InboxInputType.MARKDOWN_FILE.value
    assert result.item.title == "Preserved Title"


def test_pasted_text_creates_markdown_with_frontmatter(tmp_path):
    paths = _init_paths(tmp_path)

    result = inbox.register_pasted_text(
        paths,
        title="Pasted Inbox Note",
        body="Body from pasted text.",
        source_url="https://example.com/source",
        tags=["alpha", "beta"],
    )

    parsed = parse_page(result.stored_path.read_text(encoding="utf-8"))
    assert result.stored_path.parent == paths.inbox_text
    assert result.stored_path.suffix == ".md"
    assert parsed.frontmatter["title"] == "Pasted Inbox Note"
    assert parsed.frontmatter["input_type"] == inbox.InboxInputType.PASTED_TEXT.value
    assert parsed.frontmatter["source_url"] == "https://example.com/source"
    assert parsed.frontmatter["tags"] == ["alpha", "beta"]
    assert parsed.body.strip() == "Body from pasted text."


def test_processing_lock_updates_state_without_creating_processing_folder(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "queued.txt"
    source.write_text("Queued title\n\nQueued body.", encoding="utf-8")
    registration = inbox.register_document_file(paths, source)

    item = inbox.acquire_processing_lock(paths, registration.item.id, lock_token="lock-123")

    assert item.state == inbox.InboxState.PROCESSING.value
    assert item.lock_token == "lock-123"
    assert not (paths.inbox / "_Processing").exists()


def test_success_archive_moves_to_raw_archive_and_updates_state_event(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "archive-me.txt"
    source.write_text("Archive title\n\nArchive body.", encoding="utf-8")
    registration = inbox.register_document_file(paths, source, copy=False)
    inbox.acquire_processing_lock(paths, registration.item.id, lock_token="archive-lock")

    result = inbox.move_to_archive(paths, registration.item.id, message="Archived")

    assert result.moved is True
    assert result.source_path == paths.inbox_files / "archive-me.txt"
    assert not result.source_path.exists()
    assert result.target_path == paths.raw_archive / "archive-me.txt"
    assert result.target_path.exists()
    assert result.item.state == inbox.InboxState.ARCHIVED.value
    assert result.item.relpath == "raw/archive-me.txt"
    with db.connect(paths.state_db) as conn:
        events = inbox.list_inbox_events(conn, registration.item.id)
    assert events[-1].event_type == "moved_to_archive"
    assert events[-1].data["target_path"].endswith("raw/archive-me.txt")


def test_failure_moves_to_failed_and_writes_diagnostic_report(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "broken.md"
    source.write_text("# Broken\n\nBody.", encoding="utf-8")
    registration = inbox.register_markdown_file(paths, source, copy=False)
    inbox.acquire_processing_lock(paths, registration.item.id, lock_token="failed-lock")

    result = inbox.move_to_failed(
        paths,
        registration.item.id,
        error=RuntimeError("provider timeout\nsecret-ish line"),
        phase="extract",
        retry_hint="Retry after provider recovers.",
    )

    assert result.moved is True
    assert result.target_path == paths.inbox_failed / "broken.md"
    assert result.target_path.exists()
    assert result.item.state == inbox.InboxState.FAILED.value
    assert result.report_path is not None
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "phase: extract" in report_text
    assert "error_type: RuntimeError" in report_text
    assert "provider timeout | secret-ish line" in report_text
    assert "Retry after provider recovers." in report_text


def test_review_moves_to_review_folder(tmp_path):
    paths = _init_paths(tmp_path)
    source = tmp_path / "review.txt"
    source.write_text("Review title\n\nReview body.", encoding="utf-8")
    registration = inbox.register_document_file(paths, source, copy=False)
    inbox.acquire_processing_lock(paths, registration.item.id, lock_token="review-lock")

    result = inbox.move_to_review(paths, registration.item.id)

    assert result.moved is True
    assert result.target_path == paths.inbox_review / "review.txt"
    assert result.target_path.exists()
    assert result.item.state == inbox.InboxState.REVIEW.value
    assert result.item.relpath == "Inbox/_Review/review.txt"


def test_collision_handling_avoids_overwrite(tmp_path):
    paths = _init_paths(tmp_path)
    first = tmp_path / "duplicate.txt"
    second = tmp_path / "duplicate-second.txt"
    first.write_text("Same name title\n\nFirst body.", encoding="utf-8")
    second.write_text("Same name title\n\nSecond body.", encoding="utf-8")

    first_result = inbox.register_document_file(paths, first)
    aliased_source = tmp_path / "duplicate.txt"
    aliased_source.write_text("Conflicting source\n\nAnother body.", encoding="utf-8")
    second_result = inbox.register_document_file(paths, aliased_source)

    assert first_result.stored_path == paths.inbox_files / "duplicate.txt"
    assert second_result.stored_path == paths.inbox_files / "duplicate-1.txt"
    assert first_result.stored_path.read_text(encoding="utf-8").startswith("Same name title")
    assert second_result.stored_path.read_text(encoding="utf-8").startswith("Conflicting source")


def test_document_registration_dedupes_by_content_hash_without_creating_second_file(tmp_path):
    paths = _init_paths(tmp_path)
    first = tmp_path / "first.txt"
    duplicate = tmp_path / "duplicate.txt"
    content = "Hash title\n\nSame body for dedupe."
    first.write_text(content, encoding="utf-8")
    duplicate.write_text(content, encoding="utf-8")

    first_result = inbox.register_document_file(paths, first)
    duplicate_result = inbox.register_document_file(paths, duplicate)

    assert duplicate_result.deduped is True
    assert duplicate_result.item.id == first_result.item.id
    assert duplicate_result.stored_path == first_result.stored_path
    assert duplicate.exists()
    assert sorted(path.name for path in paths.inbox_files.iterdir()) == ["first.txt"]
    with db.connect(paths.state_db) as conn:
        items = inbox.list_inbox_items(conn)
        events = inbox.list_inbox_events(conn, first_result.item.id)
    assert len(items) == 1
    assert events[-1].event_type == "duplicate_content_hash_registered"
    assert events[-1].data["source_path"].endswith("duplicate.txt")
    assert events[-1].data["stored_path"].endswith("Inbox/Files/first.txt")
    assert events[-1].data["deduped"] is True


def test_markdown_registration_dedupes_by_content_hash_and_records_traceable_event(tmp_path):
    paths = _init_paths(tmp_path)
    first = tmp_path / "entry-a.md"
    duplicate = tmp_path / "entry-b.md"
    content = "---\ntitle: Shared Title\n---\n\n# Heading\n\nSame markdown body.\n"
    first.write_text(content, encoding="utf-8")
    duplicate.write_text(content, encoding="utf-8")

    first_result = inbox.register_markdown_file(paths, first)
    duplicate_result = inbox.register_markdown_file(paths, duplicate)

    assert duplicate_result.deduped is True
    assert duplicate_result.item.id == first_result.item.id
    assert duplicate_result.stored_path == first_result.stored_path
    assert duplicate.exists()
    assert sorted(path.name for path in paths.inbox_markdown.iterdir()) == ["entry-a.md"]
    with db.connect(paths.state_db) as conn:
        items = inbox.list_inbox_items(conn)
        events = inbox.list_inbox_events(conn, first_result.item.id)
    assert len(items) == 1
    assert events[-1].event_type == "duplicate_content_hash_registered"
    assert events[-1].data["requested_input_type"] == inbox.InboxInputType.MARKDOWN_FILE.value
    assert events[-1].data["source_preserved"] is True


def test_move_failure_records_evidence_and_preserves_source(tmp_path, monkeypatch):
    paths = _init_paths(tmp_path)
    source = tmp_path / "cannot-move.txt"
    source.write_text("Cannot move\n\nBody.", encoding="utf-8")
    registration = inbox.register_document_file(paths, source, copy=False)
    inbox.acquire_processing_lock(paths, registration.item.id, lock_token="move-lock")

    def raising_copy2(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(inbox.shutil, "copy2", raising_copy2)

    result = inbox.move_to_archive(paths, registration.item.id)

    assert result.moved is False
    assert result.source_path.exists()
    assert result.item.state == inbox.InboxState.PROCESSING.value
    with db.connect(paths.state_db) as conn:
        events = inbox.list_inbox_events(conn, registration.item.id)
    assert events[-1].event_type == "archive_move_failed"
    assert events[-1].data["source_path"].endswith("Inbox/Files/cannot-move.txt")
    assert events[-1].data["target_path"].endswith("raw/cannot-move.txt")
    assert events[-1].data["db_state"] == inbox.InboxState.PROCESSING.value
    assert events[-1].data["retryable"] is True


def test_move_to_pending_missing_source_file_returns_moved_false_and_records_event(tmp_path):
    """move_to_pending on a pending item whose file is missing (same-path case) must surface as failure.

    Regression test for STAB-001: _safe_copy_or_move same-path short-circuit was returning
    success without checking source_path.is_file(), causing move_to_pending to silently
    succeed when the physical file was already gone but relpath pointed to the same dest.
    """
    paths = _init_paths(tmp_path)
    # Register a document file - this stores it in inbox_files with PENDING state
    source = tmp_path / "pending-missing.txt"
    source.write_text("Pending Title\n\nBody.", encoding="utf-8")
    registration = inbox.register_document_file(paths, source, copy=False)
    assert registration.item.state == inbox.InboxState.PENDING.value

    # Physically delete the file while keeping the DB entry
    actual_file = paths.inbox_files / "pending-missing.txt"
    actual_file.unlink()
    assert not actual_file.exists()

    # move_to_pending should detect the missing source and return moved=False
    result = inbox.move_to_pending(paths, registration.item.id)

    assert result.moved is False
    assert result.source_path == actual_file
    assert result.item.state == inbox.InboxState.PENDING.value  # state unchanged
    with db.connect(paths.state_db) as conn:
        events = inbox.list_inbox_events(conn, registration.item.id)
    # Last event should be a failure event
    last_event = events[-1]
    assert last_event.event_type == "pending_move_failed"
    assert "Source file not found" in last_event.message
    assert last_event.data["source_path"].endswith("Inbox/Files/pending-missing.txt")
    assert last_event.data["db_state"] == inbox.InboxState.PENDING.value
    assert last_event.data["retryable"] is True


def test_cli_registration_helper_routes_markdown_and_document_files_to_inbox_subfolders(tmp_path):
    paths = _init_paths(tmp_path)
    markdown = tmp_path / "note.md"
    document = tmp_path / "paper.txt"
    markdown.write_text("# Note\n\nBody.", encoding="utf-8")
    document.write_text("Paper Title\n\nBody.", encoding="utf-8")

    markdown_result = _register_file_in_inbox(paths, markdown)
    document_result = _register_file_in_inbox(paths, document)

    assert markdown_result.item.input_type == inbox.InboxInputType.MARKDOWN_FILE.value
    assert markdown_result.item.relpath == "Inbox/Markdown/note.md"
    assert document_result.item.input_type == inbox.InboxInputType.DOCUMENT_FILE.value
    assert document_result.item.relpath == "Inbox/Files/paper.txt"


def test_web_upload_registers_files_in_inbox_not_raw(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.post(
        "/ingest/upload",
        files=[
            ("files", ("upload.md", b"# Uploaded\n\nMarkdown body.", "text/markdown")),
            ("files", ("upload.txt", b"Uploaded title\n\nBody.", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["files"][0]["relpath"] == "Inbox/Markdown/upload.md"
    assert payload["files"][0]["state"] == inbox.InboxState.PENDING.value
    assert payload["files"][0]["input_type"] == inbox.InboxInputType.MARKDOWN_FILE.value
    assert payload["files"][0]["source_id"] is None
    assert payload["files"][1]["relpath"] == "Inbox/Files/upload.txt"
    assert not (paths.raw / "upload.md").exists()
    assert not (paths.raw / "upload.txt").exists()


def test_web_paste_registers_pasted_text_in_inbox_text(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.post(
        "/ingest/paste",
        data={
            "title": "Pasted from Web",
            "body": "Body from web paste.",
            "source_url": "https://example.com/web",
            "tags": "alpha, beta",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["relpath"] == "Inbox/Text/pasted-from-web.md"
    assert payload["state"] == inbox.InboxState.PENDING.value
    assert payload["input_type"] == inbox.InboxInputType.PASTED_TEXT.value
    stored = paths.root / payload["relpath"]
    parsed = parse_page(stored.read_text(encoding="utf-8"))
    assert parsed.frontmatter["source_url"] == "https://example.com/web"
    assert parsed.frontmatter["tags"] == ["alpha", "beta"]


def test_web_upload_deduped_flag_is_false_on_first_call_true_on_second_with_same_content(tmp_path, monkeypatch):
    """Upload the same content twice; first call deduped=false, second call deduped=true, only one file exists."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    # Same content in two separate file uploads
    content = b"Same content body for dedupe test."
    first_response = client.post(
        "/ingest/upload",
        files=[("files", ("original.txt", content, "text/plain"))],
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["ok"] is True
    assert first_payload["files"][0]["deduped"] is False
    assert (paths.inbox_files / "original.txt").exists()

    # Second upload with same content should be deduped
    second_response = client.post(
        "/ingest/upload",
        files=[("files", ("duplicate.txt", content, "text/plain"))],
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["ok"] is True
    assert second_payload["files"][0]["deduped"] is True
    # Same inbox item id
    assert second_payload["files"][0]["inbox_item_id"] == first_payload["files"][0]["inbox_item_id"]
    # Only one file in Inbox/Files/ (excluding .gitkeep)
    files = [p.name for p in paths.inbox_files.iterdir() if p.name != ".gitkeep"]
    assert sorted(files) == ["original.txt"]
