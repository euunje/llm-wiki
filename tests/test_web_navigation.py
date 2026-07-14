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
    """Files synced directly into Raw Sources should become pending via web scan."""
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
    assert payload["counts"]["added"] == 1
    assert payload["pending_count"] == 1

    after = client.get("/ingest")
    assert after.status_code == 200
    assert "mobile-synced.md" in after.text
    assert "선택 항목 수집 시작" in after.text
    assert "새 Raw Source 모두 수집" in after.text
    assert "작업으로 보내기" in after.text


def test_ingest_pending_sources_render_batch_queue_actions(tmp_path, monkeypatch):
    """Pending sources should be handled as a queue with batch actions, not CLI commands."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    raw_body = ("# Raw note\n\n" + "이 문서는 수집 대기열 렌더링을 검증하기 위한 충분한 길이의 원문입니다. " * 30).encode()
    upload = client.post(
        "/ingest/upload",
        files=[("files", ("raw-note.md", raw_body, "text/markdown"))],
    )
    assert upload.status_code == 200

    response = client.get("/ingest")

    assert response.status_code == 200
    assert "수집 대기열" in response.text
    assert "선택 항목 수집 시작" in response.text
    assert "새 Raw Source 모두 수집" in response.text
    assert "작업으로 보내기" in response.text
    assert "분류/라우팅은 Raw Source 경로와 파일 유형을 기준으로" in response.text


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
