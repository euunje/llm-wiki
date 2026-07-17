"""Regression tests for web navigation consistency."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def test_jobs_page_uses_shared_sidebar_navigation(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "작업" in response.text
    for label in [
        "대시보드",
        "소스",
        "수신함",
        "수집",
        "작업",
        "질문",
        "검사",
        "그래프",
        "변경사항",
        "로그",
        "설정",
    ]:
        assert f">{label}<" in response.text
    assert "최근 작업" in response.text


def test_jobs_page_shows_inbox_item_id_and_phase_progress(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db, inbox

    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Inbox/Markdown/jobs-page.md", "hash-jobs-page", "md", 100, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.execute(
            "INSERT INTO inbox_items (source_id, input_type, state, relpath, content_hash, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                inbox.InboxInputType.MARKDOWN_FILE.value,
                inbox.InboxState.PENDING.value,
                "Inbox/Markdown/jobs-page.md",
                "hash-jobs-page",
                "Jobs Page",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        inbox_item_id = conn.execute("SELECT id FROM inbox_items").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_jobs (source_id, state, phase, progress, created_at, started_at) VALUES (?, 'running', 'extracting', 0.39, ?, ?)",
            (source_id, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    client = TestClient(create_app(paths))
    response = client.get("/jobs")

    assert response.status_code == 200
    assert f"Inbox #{inbox_item_id}" in response.text
    assert "extracting · 39%" in response.text


def test_create_app_marks_stale_jobs_interrupted(tmp_path, monkeypatch):
    """Server startup should not leave dead running jobs stuck forever."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    import sqlite3
    from llm_wiki import db

    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("10. Raw Sources/example.md", "hash", "md", 100, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_jobs (source_id, state, phase, progress, created_at, started_at) VALUES (?, 'running', 'drafting', 0.4, ?, ?)",
            (source_id, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    create_app(paths)

    with sqlite3.connect(paths.state_db) as conn:
        row = conn.execute("SELECT state, error, finished_at FROM ingest_jobs").fetchone()
    assert row[0] == "interrupted"
    assert row[1] == "Server restarted during ingest"
    assert row[2]


def test_web_job_callbacks_report_no_thinking_mode(tmp_path, monkeypatch):
    """Job progress should reflect the configured extraction thinking mode."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db
    from llm_wiki.jobs import _JobCallbacks, get_events_since

    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("10. Raw Sources/example.md", "hash", "md", 100, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_jobs (id, source_id, state, created_at) VALUES (99, ?, 'running', ?)",
            (source_id, "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    callbacks = _JobCallbacks(paths, 99, thinking_for_extraction=False)
    callbacks.on_extracting()

    events = get_events_since(paths, 99, -1)
    assert events[-1]["data"]["text"] == "Extracting candidates (no thinking)…"


def test_ingest_page_uses_model_generic_copy(tmp_path, monkeypatch):
    """Ingest page must not hard-code a specific model name in user-facing copy."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.get("/ingest")

    assert response.status_code == 200
    assert "새 입력을 Inbox에 등록하고 처리 대기열로 보냅니다" in response.text
    assert "텍스트 붙여넣기" in response.text
    assert "Inbox에 등록" in response.text
    assert "Inbox/Text" in response.text
    assert "Inbox 대기열" in response.text
    assert "Raw Sources에서 Inbox로 가져오기" in response.text
    assert "Inbox 대기 항목이 없습니다" in response.text
    assert "Qwen3가 읽는 것을 확인하세요" not in response.text
    assert "Qwen3" not in response.text


def test_ingest_page_can_live_update_job_card_progress(tmp_path, monkeypatch):
    """The ingest page should not leave cards visually stuck on old phases."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db

    client = TestClient(create_app(paths))
    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Inbox/Markdown/live-card.md", "hash-live-card", "md", 100, "2026-01-01T00:00:00+00:00", "pending"),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_jobs (source_id, state, phase, progress, created_at, started_at) VALUES (?, 'running', 'extracting', 0.20, ?, ?)",
            (source_id, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    response = client.get("/ingest")

    assert response.status_code == 200
    assert "job-state state-badge state-running" in response.text
    assert "job-progress-wrap progress-bar-bg" in response.text
    assert 'job-detail text-xs text-[#64748b] mt-1">extracting' in response.text
    assert "function updateJobCard(jobId, data)" in response.text
    assert "updateJobCard(jobId, d);" in response.text


def test_ingest_scan_registers_synced_raw_sources(tmp_path, monkeypatch):
    """Files synced directly into Raw Sources should register as Inbox pending items via web scan.

    Phase 5B: /ingest now renders Inbox pending items as the primary queue, so a freshly
    scanned inbox item should appear as a per-row entry with a per-row action button.
    """
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    synced_dir = paths.raw / "Articles"
    synced_dir.mkdir(parents=True, exist_ok=True)
    synced_file = synced_dir / "mobile-synced.md"
    synced_file.write_text(
        "# Mobile synced source\n\n"
        + "모바일 Obsidian에서 동기화된 Raw Source를 웹 수집 대기열에 등록하는 검증 문장입니다. " * 30,
        encoding="utf-8",
    )
    client = TestClient(create_app(paths))

    before = client.get("/ingest")
    assert before.status_code == 200
    assert "mobile-synced.md" not in before.text

    scan = client.post("/ingest/scan")
    assert scan.status_code == 200
    payload = scan.json()
    # Phase 5A Inbox-first scan response: `added` alias kept for the deprecation window.
    assert payload["counts"]["added"] == 1
    # `pending_count` is computed from `inbox_items.state = pending`.
    assert payload["pending_count"] == 1
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert result["result"] == "registered"
    assert result["inbox_item_id"] > 0
    assert result["relpath"] == "Inbox/Markdown/mobile-synced.md"
    assert result["state"] == "pending"
    # `source_id` is materialized at /ingest/start time, not at scan time.
    assert result["source_id"] is None

    after = client.get("/ingest")
    assert after.status_code == 200
    # Phase 5B: Inbox pending items render as per-row entries in the queue.
    assert "Inbox 대기열" in after.text
    assert "Raw Sources에서 Inbox로 가져오기" in after.text
    assert "선택 처리 시작" in after.text
    assert "전체 처리" in after.text
    assert "mobile-synced.md" in after.text
    assert "작업으로 보내기" in after.text
    assert "markdown_file" in after.text
    assert "pending" in after.text


def test_ingest_page_shows_error_sources_as_retryable_queue_items(tmp_path, monkeypatch):
    """Previously failed sources are already scanned, so they must remain visible for retry."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    from llm_wiki import db

    db.init_db(paths.state_db)
    synced_dir = paths.raw / "Articles"
    synced_dir.mkdir(parents=True, exist_ok=True)
    synced_file = synced_dir / "AlexsJones-Ilmfit.md"
    synced_file.write_text(
        "# AlexsJones Ilmfit\n\n" + "이미 등록됐지만 실패한 소스가 재시도 대기열에 보여야 합니다. " * 30,
        encoding="utf-8",
    )
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("10. Raw Sources/Articles/AlexsJones-Ilmfit.md", "hash-error", "md", synced_file.stat().st_size, "2026-01-01T00:00:00+00:00", "error"),
        )
        conn.commit()

    client = TestClient(create_app(paths))
    response = client.get("/ingest")

    assert response.status_code == 200
    assert "AlexsJones-Ilmfit.md" in response.text
    assert "재시도 필요" in response.text
    assert "작업으로 보내기" in response.text


def test_ingest_pending_sources_render_batch_queue_actions(tmp_path, monkeypatch):
    """Uploaded sources should be registered as Inbox pending items and rendered in /ingest.

    Phase 5B: /ingest now renders Inbox pending items as the primary queue, so a freshly
    uploaded inbox item should appear as a per-row entry with a per-row action button.
    """
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    raw_body = ("# Raw note\n\n" + "이 문서는 수집 대기열 렌더링을 검증하기 위한 충분한 길이의 원문입니다. " * 30).encode()
    upload = client.post(
        "/ingest/upload",
        files=[("files", ("raw-note.md", raw_body, "text/markdown"))],
    )
    assert upload.status_code == 200
    upload_payload = upload.json()
    # Phase 5A Inbox-first upload response.
    assert upload_payload["ok"] is True
    assert len(upload_payload["files"]) == 1
    file_row = upload_payload["files"][0]
    assert file_row["filename"] == "raw-note.md"
    assert file_row["inbox_item_id"] > 0
    assert file_row["relpath"] == "Inbox/Markdown/raw-note.md"
    assert file_row["state"] == "pending"
    # `source_id` is materialized at /ingest/start time, not at upload time.
    assert file_row["source_id"] is None

    response = client.get("/ingest")

    assert response.status_code == 200
    # Phase 5B: Inbox pending items render as per-row entries in the queue.
    assert "Inbox 대기열" in response.text
    assert "선택 처리 시작" in response.text
    assert "전체 처리" in response.text
    assert "raw-note.md" in response.text
    assert "작업으로 보내기" in response.text
    assert "markdown_file" in response.text
    assert "pending" in response.text


def test_mobile_menu_button_and_drawer_present(tmp_path, monkeypatch):
    """Mobile shell: topbar hamburger button and right-side drawer exist."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.get("/jobs")

    assert response.status_code == 200
    # Mobile hamburger button and Korean accessibility labels.
    assert 'id="mobile-menu-button"' in response.text
    assert 'aria-label="탐색 메뉴 열기"' in response.text
    assert 'aria-label="주 탐색"' in response.text
    assert 'aria-label="메뉴 닫기"' in response.text
    assert "mobile-menu-panel" in response.text
    assert "mobile-menu-backdrop" in response.text
    assert "탐색" in response.text
    # Drawer nav entries match the sidebar labels
    for label in [
        "대시보드",
        "소스",
        "수신함",
        "수집",
        "작업",
        "질문",
        "검사",
        "그래프",
        "변경사항",
        "로그",
        "설정",
    ]:
        assert f">{label}<" in response.text
    # No bottom-tab navigation shell was introduced.
    forbidden_bottom_nav_markers = [
        'id="mobile-bottom-nav"',
        'id="bottom-nav"',
        'class="bottom-nav',
        'data-mobile-bottom-nav',
        'fixed bottom-0',
    ]
    for marker in forbidden_bottom_nav_markers:
        assert marker not in response.text
    # Desktop sidebar still present (hidden on mobile but exists in markup)
    assert 'class="hidden md:flex w-60' in response.text


def test_lint_fix_stream_emits_progress_and_completion(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    from llm_wiki import search
    monkeypatch.setattr(search, "update_index", lambda *args, **kwargs: None)
    paths = scaffold(tmp_path)
    (paths.sources / "alpha.md").write_text(
        "---\n"
        "title: Alpha Source\n"
        "type: source\n"
        "created: 2026-01-01\n"
        "---\n\n"
        "# Alpha Source\n",
        encoding="utf-8",
    )
    entity_path = paths.entities / "stream-test.md"
    entity_path.write_text(
        "---\n"
        "title: Stream Test\n"
        "type: entity\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "sources:\n"
        "- sources/alpha.md\n"
        "---\n\n"
        "# Stream Test\n\n"
        "See [[sources/alpha.md]].\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(paths))

    with client.stream("GET", "/lint/fix/stream") as response:
        body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert "event: progress" in body
    assert "event: complete" in body
    chunks = [chunk for chunk in body.strip().split("\n\n") if chunk.strip()]
    payloads: dict[str, list[dict]] = {}
    for chunk in chunks:
        lines = chunk.splitlines()
        event = lines[0].split(": ", 1)[1]
        data = json.loads(lines[1].split(": ", 1)[1])
        payloads.setdefault(event, []).append(data)

    complete = payloads["complete"][-1]
    assert complete["phase"] == "complete"
    assert complete["progress"] == 1.0
    assert complete["fixed_count"] >= 1
    assert complete["remaining_fixable"] == 0
    assert complete["redirect_url"] == "/lint"
    assert "[[sources/alpha]]" in entity_path.read_text(encoding="utf-8")


def test_lint_fix_post_preserves_sync_template_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    from llm_wiki import search
    monkeypatch.setattr(search, "update_index", lambda *args, **kwargs: None)
    paths = scaffold(tmp_path)
    (paths.sources / "beta.md").write_text(
        "---\n"
        "title: Beta Source\n"
        "type: source\n"
        "created: 2026-01-01\n"
        "---\n\n"
        "# Beta Source\n",
        encoding="utf-8",
    )
    entity_path = paths.entities / "post-fix.md"
    entity_path.write_text(
        "---\n"
        "title: Post Fix\n"
        "type: entity\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "sources:\n"
        "- sources/beta.md\n"
        "---\n\n"
        "# Post Fix\n\n"
        "See [[sources/beta.md]].\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(paths))

    response = client.post("/lint/fix")

    assert response.status_code == 200
    assert "검사" in response.text
    assert "[[sources/beta]]" in entity_path.read_text(encoding="utf-8")
