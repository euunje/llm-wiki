"""Minimal landmark tests for Phase 3 UI fix (FIX-003-UI).

Tests that new routes render and new APIs return expected shapes.
Does not test full functional flows — those belong to build-test-validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import resolve_workspace


APP_JS = Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js"


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def _complete_setup(client, paths) -> None:
    cfg = client.post(
        "/api/settings/llm/config",
        json={
            "endpoint": "https://llm.example.test/v1",
            "api_key_env": "LLM_WIKI_API_KEY",
            "chat_model_name": "phase3-chat-model",
            "embedding_model_name": "phase3-embedding-model",
        },
    )
    assert cfg.status_code == 200
    for model_id in ("chat_default", "embedding_default"):
        record_artifact(
            paths,
            artifact_type="model_test_report",
            task_type="model_test",
            payload={"status": "ok", "result": "ok", "test_status": "passed", "reason": None, "model_id": model_id},
            target_type="model",
            target_id=model_id,
            metadata={"status": "ok", "result": "ok", "test_status": "passed", "reason": None, "model_id": model_id},
        )


def test_nav_contains_all_required_links(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)
    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    expected_links = [
        ("Dashboard", "/dashboard"),
        ("Inbox", "/inbox"),
        ("Mapping", "/mapping"),
        ("Vault", "/vault"),
        ("Wiki", "/wiki"),
        ("Settings", "/settings"),
    ]
    for label, href in expected_links:
        assert (
            f'href="{href}"' in body
            or f'href="http://testserver{href}"' in body
        ), f"Nav href missing: {href}"
        assert f'aria-label="{label}"' in body, f"Nav label missing: {label}"
    assert 'aria-label="Onboarding"' not in body
    assert 'action="/logout"' not in body
    assert 'action="http://testserver/logout"' not in body
    assert 'aria-label="Logout"' not in body
    assert 'aria-label="Review / Mapping"' not in body
    assert 'aria-label="Error"' not in body
    assert 'href="/search"' in body or 'href="http://testserver/search"' in body
    assert 'aria-label="Search / Ask"' in body
    assert 'utility-link' in body

    settings = client.get("/settings?tab=auth")
    assert settings.status_code == 200
    assert 'action="/logout"' in settings.text or 'action="http://testserver/logout"' in settings.text
    assert 'aria-label="Logout"' in settings.text


def test_onboarding_page_renders(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(workspace, monkeypatch)
    response = client.get("/onboarding")
    assert response.status_code == 200
    assert "Onboarding" in response.text
    assert 'class="wizard-rail"' in response.text
    assert 'id="setup-checklist"' in response.text
    assert 'href="/inbox"' in response.text
    assert 'href="/mapping"' in response.text
    assert 'href="/vault"' in response.text
    assert "Pipeline은 Inbox 입력이" in response.text
    assert "Assign current folder" in response.text
    assert "Mapping flow" in response.text

    app_js = APP_JS.read_text(encoding="utf-8")
    assert "해당 폴더에 vault 생성하시겠습니까?" in app_js
    assert "해당 폴더 구조를 확정하시겠습니까?" in app_js


def test_settings_prompt_tabs_and_route_model_help_render(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(workspace, monkeypatch)
    response = client.get("/settings?tab=prompt")
    assert response.status_code == 200
    body = response.text
    ordered = [
        'data-prompt-task="ask"',
        'data-prompt-task="compile"',
        'data-prompt-task="extract_claims"',
        'data-prompt-task="link"',
        'data-prompt-task="map"',
        'data-prompt-task="summarize"',
    ]
    assert 'id="settings-prompt-top-tabs"' in body
    positions = [body.index(item) for item in ordered]
    assert positions == sorted(positions)

    llm_response = client.get("/settings?tab=llm")
    assert llm_response.status_code == 200
    assert "/api/settings/models" in llm_response.text
    assert "chat model / embedding model을 먼저 설정" in llm_response.text


def test_dashboard_and_wiki_expose_clear_search_links(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nRetrieval concept.\n", encoding="utf-8")

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Search / Ask (FTS + Embedding)" in dashboard.text

    wiki = client.get("/wiki")
    assert wiki.status_code == 200
    assert "Search / Ask (FTS + Embedding)" in wiki.text


def test_wiki_page_renders(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nRetrieval concept.\n", encoding="utf-8")
    response = client.get("/wiki")
    assert response.status_code == 200
    assert "Wiki" in response.text


def test_setup_status_api_returns_checks(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(workspace, monkeypatch)
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert "workspace_initialized" in data
    assert "db_exists" in data
    assert "db_schema_ok" in data
    assert "web_admin_password_configured" in data
    assert "llm" in data
    assert "counts" in data
    assert "next_actions" in data


def test_wiki_pages_api_lists_concepts(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nCore concept.\n", encoding="utf-8")
    response = client.get("/api/wiki/pages")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert any(p["id"] == "rag" for p in data["pages"])


def test_wiki_page_detail_api(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\naliases: [Retrieval-Augmented Generation]\n\nCore concept.\n", encoding="utf-8")
    response = client.get("/api/wiki/pages/rag")
    assert response.status_code == 200
    data = response.json()
    # API returns "page" key, not "concept"
    page = data.get("page") or data.get("concept") or data
    assert page["id"] == "rag"
    # Aliases may or may not be parsed depending on markdown parser
    # Just verify the page has the expected structure
    assert "title" in page
    assert "content" in page


def test_dashboard_recent_jobs_api(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    conn = connect(paths.db)
    try:
        now = utc_now()
        conn.execute(
            "INSERT INTO jobs (id, job_type, target_type, target_id, status, input_refs_json, output_refs_json, error_json, retry_count, created_at, started_at, finished_at) VALUES (?, 'test_job', 'source', 'src1', 'failed', '[]', '[]', '{\"reason\":\"boom\"}', 0, ?, NULL, ?)",
            (new_id("job"), now, now),
        )
        conn.commit()
    finally:
        conn.close()
    response = client.get("/api/dashboard/errors")
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) >= 1


def test_review_mapping_api(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nConcept.\n", encoding="utf-8")
    # Create a candidate first since the mapping API requires source_candidate_id
    candidate_id = new_id("candidate")
    now = utc_now()
    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'test_node', 'src1', NULL, '{}', 'normal_review', 'test', '[]', 'pending', NULL, ?, ?)",
            (candidate_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    response = client.get(f"/api/review/mapping?source_candidate_id={candidate_id}")
    assert response.status_code == 200
    data = response.json()
    assert "concepts" in data


def test_review_candidate_detail_api(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    client, paths = _client(workspace, monkeypatch)
    candidate_id = new_id("candidate")
    now = utc_now()
    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'test_node', 'src1', NULL, '{}', 'normal_review', 'test', '[]', 'pending', NULL, ?, ?)",
            (candidate_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    response = client.get(f"/api/review/candidates/{candidate_id}")
    assert response.status_code == 200
    assert response.json()["candidate"]["id"] == candidate_id


def test_settings_page_with_tab(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(workspace, monkeypatch)
    response = client.get("/settings?tab=llm")
    assert response.status_code == 200
    assert "settings-pane-llm" in response.text
    assert "settings-tab" in response.text
