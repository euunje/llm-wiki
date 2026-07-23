"""Focused tests for WU-006: Operational State Visibility UI.

Tests verify that:
1. Dashboard/Mapping/Search/Ask/Vault distinguish setup_missing, no_data, processing, success, failure, blocked states.
2. Silent fallback is avoided — missing fields render explicit blocked/unknown state.
3. Inbox surfaces job/result/error artifacts and mapping effect statuses.
4. Navigation order and WU-002 behavior preserved (Onboarding hidden after setup complete).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import resolve_workspace


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


def test_app_js_contains_state_visibility_helpers() -> None:
    """WU-006: app.js must contain state visibility helpers."""
    script = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    # State visibility helpers
    assert "renderStateBanner" in script
    assert "classifySetupState" in script
    assert "classifyComponentStatus" in script
    assert "safeStatusPill" in script

    # State kinds
    assert "setup_missing" in script
    assert "no_data" in script
    assert "processing" in script
    assert "success" in script
    assert "failure" in script
    assert "blocked" in script
    assert "unknown" in script


def test_app_js_avoids_silent_fallback_for_missing_fields() -> None:
    """WU-006: app.js must not silently fallback missing fields to success-like states."""
    script = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    # Dashboard should check setup status explicitly
    assert "classifySetupState(setupData)" in script
    assert 'setupState === "setup_missing"' in script

    # Mapping should check setup status explicitly
    assert "setup_missing" in script
    assert "no_data" in script

    # Search/Ask should check LLM status explicitly
    assert "llmReady" in script
    assert "llmStatus" in script


def test_css_contains_state_banner_styles() -> None:
    """WU-006: style.css must contain state banner styles."""
    css = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/css/style.css").read_text(encoding="utf-8")

    assert ".state-banner" in css
    assert ".state-banner-icon" in css
    assert ".state-banner-body" in css
    assert ".state-banner-label" in css
    assert ".state-banner-message" in css
    assert ".state-banner-action" in css
    assert ".state-banner.state-ok" in css
    assert ".state-banner.state-warn" in css
    assert ".state-banner.state-bad" in css
    assert ".state-banner.state-muted" in css


def test_dashboard_template_has_state_containers(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Dashboard template must have state containers."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert 'data-state-container="attention"' in response.text
    assert 'data-state-container="system"' in response.text
    assert 'data-state-container="activity"' in response.text


def test_mapping_template_has_state_containers(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Mapping template must have state containers."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/mapping")
    assert response.status_code == 200
    assert 'data-state-container="mapping-queue"' in response.text
    assert 'id="mapping-node-list"' in response.text
    assert 'id="mapping-node-editor"' in response.text
    assert '매핑 노드 검토 / Mapping Node Review' in response.text
    assert '노드명, 실제 Wiki 문서 Frontmatter, 본문' in response.text


def test_search_template_has_state_containers(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Search template must have state containers."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/search")
    assert response.status_code == 200
    assert 'data-state-container="search-results"' in response.text
    assert 'data-state-container="ask-result"' in response.text


def test_vault_template_has_state_containers(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Vault template must have state containers."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/vault")
    assert response.status_code == 200
    assert 'data-state-container="vault-tree"' in response.text
    assert 'data-state-container="vault-viewer"' in response.text


def test_inbox_template_has_state_containers(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Inbox template must have state containers."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/inbox")
    assert response.status_code == 200
    assert 'data-state-container="inbox-list"' in response.text
    assert 'data-state-container="inbox-detail"' in response.text
    assert 'data-state-container="inbox-queue"' in response.text


def test_setup_status_api_returns_needs_onboarding_field(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: /api/setup/status must return needs_onboarding field for UI state classification."""
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    payload = response.json()
    assert "needs_onboarding" in payload
    assert "setup_complete" in payload
    assert "llm" in payload
    assert "vault" in payload
    assert "components" in payload


def test_dashboard_metrics_api_returns_vault_status_field(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: /api/dashboard/metrics must return vault_status field for UI state classification."""
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert "vault_status" in payload
    assert "vault_ready" in payload
    assert "llm_status" in payload


def test_inbox_items_api_returns_status_field(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: /api/inbox/items must return status field for UI state classification."""
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/api/inbox/items")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    for item in payload["items"]:
        assert "status" in item
        assert item["status"] in {"new", "processing", "needs_mapping", "failed", "completed"}


def test_mapping_candidates_api_returns_status_field(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: /api/mapping/candidates must return status field for UI state classification."""
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/api/mapping/candidates")
    assert response.status_code == 200
    payload = response.json()
    assert "candidates" in payload
    for candidate in payload["candidates"]:
        assert "status" in candidate


def test_onboarding_hidden_after_setup_complete(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Onboarding nav must be hidden after setup complete (WU-002 behavior preserved)."""
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/dashboard")
    assert response.status_code == 200
    # Onboarding should be hidden after setup complete
    assert 'aria-label="Onboarding"' not in response.text


def test_onboarding_visible_when_setup_incomplete(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WU-006: Onboarding nav must be visible when setup incomplete."""
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/dashboard")
    assert response.status_code == 200
    # Onboarding should be visible when setup incomplete
    assert 'aria-label="Onboarding"' in response.text


def test_app_js_no_hardcoded_localhost_or_secrets() -> None:
    """WU-006: app.js must not contain hardcoded localhost or secrets."""
    script = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    assert "localhost" not in script
    assert "127.0.0.1" not in script
    assert "LLM_WIKI_WEB_ADMIN_PASSWORD" not in script
    assert "LLM_WIKI_API_KEY" not in script
