from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("LLM_WIKI_API_KEY", "super-secret-token")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def test_settings_apis_manage_prompt_versions_and_mask_model_settings(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)

    initial = client.get("/api/settings/prompt-versions?task_type=extract_claims")
    assert initial.status_code == 200
    assert initial.json()["count"] >= 1

    created = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "web-test-v1",
            "prompt_text": (
                "Return JSON candidate output for extract_claims with claim, node, "
                "evidence, and JSON fields so schema validation passes."
            ),
            "change_note": "via web api",
        },
    )
    assert created.status_code == 200
    assert created.json()["test_status"] == "passed"
    prompt_id = created.json()["prompt_id"]

    confirmed = client.post(f"/api/settings/prompt-versions/{prompt_id}/confirm")
    assert confirmed.status_code == 200

    after = client.get("/api/settings/prompt-versions?task_type=extract_claims")
    confirmed_rows = [row for row in after.json()["prompt_versions"] if row["id"] == prompt_id]
    assert confirmed_rows[0]["state"] == "confirmed"

    prompt_groups = client.get("/api/settings/prompts?task_type=extract_claims")
    assert prompt_groups.status_code == 200
    assert prompt_groups.json()["task_groups"][0]["confirmed"]["id"] == prompt_id

    history = client.get("/api/settings/prompts/history?task_type=extract_claims")
    assert history.status_code == 200
    assert any(row["id"] == prompt_id for row in history.json()["history"])

    models = client.get("/api/settings/models")
    assert models.status_code == 200
    payload = models.json()
    assert payload["routes"]["extract_claims"] == "chat_default"
    assert payload["settings"]["api_key_env"] == "LL***EY"

    llm_status = client.get("/api/settings/llm/status")
    assert llm_status.status_code == 200
    assert llm_status.json()["routes"]["extract_claims"] == "chat_default"

    route = client.post("/api/settings/llm/route", json={"task_type": "summarize", "model_id": "chat_default"})
    assert route.status_code == 200
    assert route.json()["route"]["task_type"] == "summarize"

    vault = client.get("/api/settings/vault")
    assert vault.status_code == 200
    assert vault.json()["onboarding_path"] == "/onboarding"

    auth = client.get("/api/settings/auth")
    assert auth.status_code == 200
    assert auth.json()["web_admin_password_configured"] is True

    prompt_test_artifacts = list((paths.artifacts / "prompt_confirm_test" / prompt_id).glob("*.json"))
    assert prompt_test_artifacts
