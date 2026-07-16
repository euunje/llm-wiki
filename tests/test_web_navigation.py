"""Regression tests for web navigation consistency."""

from __future__ import annotations

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
    assert "소스를 업로드하고 모델이 읽을 수 있는 작업 대기열로 보냅니다" in response.text
    assert "수집 대기열" in response.text
    assert "Raw Sources 스캔" in response.text
    assert "현재 등록된 대기 항목이 없습니다" in response.text
    assert "Qwen3가 읽는 것을 확인하세요" not in response.text
    assert "Qwen3" not in response.text


def test_ingest_scan_registers_synced_raw_sources(tmp_path, monkeypatch):
    """Files synced directly into Raw Sources should register as Inbox pending items via web scan.

    Phase 5A contract: /ingest/scan imports supported files into Inbox (no longer creates
    legacy `sources` rows). The /ingest HTML template still iterates `pending` as `sources`
    rows, so the freshly registered inbox item is not yet rendered as a per-row entry — that
    template alignment is owned by Phase 5B. This regression test therefore asserts the
    Inbox-first scan API contract and the page-level queue copy/buttons that remain on
    /ingest regardless of pending items.
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
    # Page-level queue copy/buttons are always rendered regardless of pending items.
    assert "수집 대기열" in after.text
    assert "Raw Sources 스캔" in after.text
    assert "선택 항목 수집 시작" in after.text
    assert "대기/재시도 모두 수집" in after.text
    assert "분류/라우팅은 Raw Source 경로와 파일 유형을 기준으로" in after.text
    # Phase 5A boundary: the /ingest template still iterates legacy `sources` rows,
    # so a freshly scanned inbox item does not yet render as a per-row entry.
    # Per-row "작업으로 보내기" rendering for inbox items is owned by Phase 5B.
    assert "mobile-synced.md" not in after.text
    assert "작업으로 보내기" not in after.text


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
    """Uploaded sources should be registered as Inbox pending items, not legacy sources rows.

    Phase 5A contract: /ingest/upload returns the Inbox-first payload (inbox_item_id,
    relpath, state, source_id) and registers an inbox_items row instead of a legacy
    sources row. The /ingest HTML template still iterates `pending` as `sources` rows,
    so the freshly uploaded inbox item is not yet rendered as a per-row entry — that
    template alignment is owned by Phase 5B. This regression test therefore asserts the
    Inbox-first upload API contract and the page-level batch-action copy/buttons that
    remain on /ingest regardless of pending items.
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
    # Page-level queue copy/buttons are always rendered regardless of pending items.
    assert "수집 대기열" in response.text
    assert "선택 항목 수집 시작" in response.text
    assert "대기/재시도 모두 수집" in response.text
    assert "분류/라우팅은 Raw Source 경로와 파일 유형을 기준으로" in response.text
    # Phase 5A boundary: the /ingest template still iterates legacy `sources` rows,
    # so a freshly uploaded inbox item does not yet render as a per-row entry.
    # Per-row "작업으로 보내기" rendering for inbox items is owned by Phase 5B.
    assert "raw-note.md" not in response.text
    assert "작업으로 보내기" not in response.text


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
