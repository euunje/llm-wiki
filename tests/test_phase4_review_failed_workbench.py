from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki import config as cfg
from llm_wiki import db, inbox
from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def _init_paths(tmp_path: Path) -> cfg.WikiPaths:
    scaffold(tmp_path)
    paths = cfg.WikiPaths(tmp_path)
    db.init_db(paths.state_db)
    return paths


def _make_failed_item(paths: cfg.WikiPaths, *, filename: str = "failed-note.md") -> inbox.InboxItem:
    source = paths.root / filename
    source.write_text(
        f"---\ntitle: Failed Note {filename}\n---\n\nBody for failed note from {filename}.\n",
        encoding="utf-8",
    )
    registration = inbox.register_markdown_file(paths, source, copy=False)
    inbox.acquire_processing_lock(paths, registration.item.id, lock_token="failed-lock")
    result = inbox.move_to_failed(paths, registration.item.id, error=RuntimeError("provider timeout"), phase="extract")
    assert result.report_path is not None
    with db.connect(paths.state_db) as conn:
        item = inbox.get_inbox_item(conn, registration.item.id)
    assert item is not None
    return item


def test_inbox_route_builds_unified_workbench_context_and_preserves_legacy_items(tmp_path):
    paths = _init_paths(tmp_path)
    (paths.non_categories / "legacy-review.md").write_text(
        "---\ntitle: Legacy Review\nconfidence: low\nsuggestedExternalOwner: legacy-owner\nsource_file: sources/legacy.md\nprocessed_at: 2026-07-15T00:00:00Z\n---\n\nLegacy body.\n",
        encoding="utf-8",
    )

    pending_source = paths.root / "pending.txt"
    pending_source.write_text("Pending Title\n\nPending body.", encoding="utf-8")
    inbox.register_document_file(paths, pending_source, copy=False).item

    review_source = paths.root / "review.md"
    review_source.write_text("---\ntitle: Review DB\n---\n\nReview body.\n", encoding="utf-8")
    review_item = inbox.register_markdown_file(paths, review_source, copy=False).item
    inbox.acquire_processing_lock(paths, review_item.id, lock_token="review-lock")
    inbox.move_to_review(paths, review_item.id)

    failed_item = _make_failed_item(paths)

    client = TestClient(create_app(paths))
    response = client.get(f"/inbox?state=failed&selected=db:{failed_item.id}")

    assert response.status_code == 200
    assert "Legacy Review" in response.text
    assert "legacy-owner" in response.text
    assert "legacy-review" in [item.slug for item in response.context["items"]]
    assert response.context["filter_state"] == "failed"
    assert response.context["counts"] == {"all": 4, "pending": 2, "review": 1, "failed": 1}
    assert [item["item_id"] for item in response.context["workbench_items"]] == [failed_item.id]
    assert response.context["selected_item"].key == f"db:{failed_item.id}"
    assert "provider timeout" in response.context["selected_detail"].diagnostic["content"]

    default_filtered_response = client.get("/inbox?state=failed")
    assert default_filtered_response.status_code == 200
    assert default_filtered_response.context["workbench_items"][0]["item_id"] == failed_item.id
    assert default_filtered_response.context["selected_item"].key == f"db:{failed_item.id}"


def test_failed_diagnostic_delete_removes_only_sidecar(tmp_path):
    paths = _init_paths(tmp_path)
    failed_item = _make_failed_item(paths, filename="diagnostic-target.md")
    client = TestClient(create_app(paths))

    source_path = paths.inbox_failed / "diagnostic-target.md"
    diagnostic_path = paths.inbox_failed / "diagnostic-target.md.diagnostic.md"
    assert source_path.exists()
    assert diagnostic_path.exists()

    get_response = client.get(f"/api/inbox/items/{failed_item.id}/diagnostic")
    delete_response = client.delete(f"/api/inbox/items/{failed_item.id}/diagnostic")

    assert get_response.status_code == 200
    assert "provider timeout" in get_response.json()["diagnostic"]["content"]
    assert delete_response.status_code == 200
    assert delete_response.json()["action"] == "diagnostic_delete"
    assert source_path.exists()
    assert not diagnostic_path.exists()


def test_diagnostic_response_respects_size_cap(tmp_path):
    """Diagnostic endpoint caps content at MAX_DIAGNOSTIC_BYTES and sets truncated flag."""
    from llm_wiki.webapp.routes.inbox import MAX_DIAGNOSTIC_BYTES

    paths = _init_paths(tmp_path)
    client = TestClient(create_app(paths))

    # Case 1: small diagnostic fits within cap -> truncated: False
    small_item = _make_failed_item(paths, filename="small-diag.md")
    resp_small = client.get(f"/api/inbox/items/{small_item.id}/diagnostic")
    assert resp_small.status_code == 200
    payload_small = resp_small.json()
    assert payload_small["truncated"] is False
    assert len(payload_small["diagnostic"]["content"]) <= MAX_DIAGNOSTIC_BYTES

    # Case 2: large diagnostic exceeds cap -> truncated: True and content capped
    large_item = _make_failed_item(paths, filename="large-diag.md")
    large_diagnostic_path = paths.inbox_failed / "large-diag.md.diagnostic.md"
    # Replace with content that exceeds MAX_DIAGNOSTIC_BYTES
    large_content = "x" * (MAX_DIAGNOSTIC_BYTES + 4096)
    large_diagnostic_path.write_text(large_content, encoding="utf-8")

    resp_large = client.get(f"/api/inbox/items/{large_item.id}/diagnostic")
    assert resp_large.status_code == 200
    payload_large = resp_large.json()
    assert payload_large["truncated"] is True
    assert len(payload_large["diagnostic"]["content"]) == MAX_DIAGNOSTIC_BYTES
    assert payload_large.get("cap_bytes") == MAX_DIAGNOSTIC_BYTES


def test_retry_hold_and_delete_contracts_for_db_backed_items(tmp_path):
    paths = _init_paths(tmp_path)
    client = TestClient(create_app(paths))

    failed_item = _make_failed_item(paths, filename="retry-me.md")
    retry_response = client.post(f"/api/inbox/items/{failed_item.id}/retry")
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["action"] == "retry"
    assert retry_payload["item"]["state"] == "pending"
    assert retry_payload["diagnostic_deleted"] is True
    assert retry_payload["item"]["relpath"] == "Inbox/Markdown/retry-me.md"
    assert (paths.inbox_markdown / "retry-me.md").exists()
    assert not (paths.inbox_failed / "retry-me.md").exists()

    hold_source = paths.root / "hold-me.txt"
    hold_source.write_text("Hold Me\n\nArchive body.", encoding="utf-8")
    hold_item = inbox.register_document_file(paths, hold_source, copy=False).item
    hold_response = client.post(f"/api/inbox/items/{hold_item.id}/hold")
    assert hold_response.status_code == 200
    hold_payload = hold_response.json()
    assert hold_payload["action"] == "hold"
    assert hold_payload["item"]["state"] == "archived"
    assert (paths.raw_archive / "hold-me.txt").exists()
    assert not (paths.inbox_files / "hold-me.txt").exists()

    delete_item = _make_failed_item(paths, filename="delete-me.md")
    delete_response = client.delete(f"/api/inbox/items/{delete_item.id}")
    assert delete_response.status_code == 200
    delete_payload = delete_response.json()
    assert delete_payload["action"] == "delete"
    assert delete_payload["source_deleted"] is True
    assert delete_payload["diagnostic_deleted"] is True
    assert not (paths.inbox_failed / "delete-me.md").exists()
    assert not (paths.inbox_failed / "delete-me.md.diagnostic.md").exists()
    with db.connect(paths.state_db) as conn:
        assert inbox.get_inbox_item(conn, delete_item.id) is None
