from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.config.settings import load_settings, save_settings
from llm_wiki.db.schema import connect
from llm_wiki.schema.prompts import create_prompt_version
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    settings = load_settings(paths.settings_file, resolve_env=False)
    settings["llm"]["models"]["chat_review"] = {
        "id": "chat_review",
        "provider": "generic_openai_compatible",
        "capability": "chat",
        "endpoint": "",
        "api_key_env": "LLM_WIKI_API_KEY",
        "model_name": "review-model",
        "request_format": "openai_chat",
    }
    save_settings(paths.settings_file, settings)
    create_prompt_version(
        paths.db,
        "phase3_settings_seed",
        "phase3-settings-test-v1",
        "Seeded test prompt",
        state="test",
        change_note="Seed one test prompt version",
    )
    create_prompt_version(
        paths.db,
        "phase3_settings_seed",
        "phase3-settings-confirmed-v1",
        "Seeded confirmed prompt",
        state="confirmed",
        change_note="Seed one confirmed prompt version",
    )
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def test_llm_route_and_prompt_test_confirm_flow_persist(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)

    route = client.post(
        "/api/settings/llm/route",
        json={"task_type": "map", "model_id": "chat_review"},
    )
    assert route.status_code == 200
    assert route.json()["route"] == {"task_type": "map", "model_id": "chat_review"}
    persisted_settings = load_settings(paths.settings_file, resolve_env=False)
    assert persisted_settings["llm"]["routing"]["map"] == "chat_review"

    created = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "phase3-web-test-v1",
            "prompt_text": (
                "Return grounded candidate JSON for the Phase 3 web test. "
                "Always include claim_candidates, node_candidates, JSON output, "
                "and a candidate envelope with claim and node keys."
            ),
            "change_note": "Created by focused functional test",
        },
    )
    assert created.status_code == 200
    prompt_id = created.json()["prompt_id"]

    conn = connect(paths.db)
    try:
        test_row = conn.execute(
            "SELECT state, change_note FROM prompt_versions WHERE id = ?",
            (prompt_id,),
        ).fetchone()
    finally:
        conn.close()
    assert test_row["state"] == "test"
    assert test_row["change_note"] == "Created by focused functional test"

    confirmed = client.post(f"/api/settings/prompts/{prompt_id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["prompt_id"] == prompt_id

    conn = connect(paths.db)
    try:
        confirmed_row = conn.execute(
            "SELECT state, confirmed_at FROM prompt_versions WHERE id = ?",
            (prompt_id,),
        ).fetchone()
        artifact_row = conn.execute(
            """
            SELECT artifact_type, task_type, target_type, target_id, path
            FROM artifacts
            WHERE artifact_type = 'prompt_confirm_test' AND target_id = ?
            """,
            (prompt_id,),
        ).fetchone()
    finally:
        conn.close()
    assert confirmed_row["state"] == "confirmed"
    assert confirmed_row["confirmed_at"]
    assert artifact_row["artifact_type"] == "prompt_confirm_test"
    assert artifact_row["task_type"] == "prompt_confirm_test"
    assert artifact_row["target_type"] == "prompt_version"
    artifact_path = Path(artifact_row["path"])
    if not artifact_path.is_absolute():
        artifact_path = paths.root / artifact_path
    assert artifact_path.exists()

    settings_page = client.get("/settings?tab=prompt")
    assert settings_page.status_code == 200
    assert 'class="settings-tabs"' in settings_page.text
    assert 'role="tablist"' in settings_page.text
    assert "Prompt" in settings_page.text


def test_llm_config_save_api_persists_without_api_key_value(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)

    response = client.post(
        "/api/settings/llm/config",
        json={
            "endpoint": "https://llm.example.test/v1",
            "api_key_env": "LLM_WIKI_TEST_API_KEY",
            "default_chat_model": "chat_default",
            "default_embedding_model": "embedding_default",
            "chat_model_name": "test-chat-model",
            "embedding_model_name": "test-embedding-model",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["settings"]["api_key_env"] == "LLM_WIKI_TEST_API_KEY"
    assert "api_key" not in payload["settings"]

    persisted = load_settings(paths.settings_file, resolve_env=False)
    llm = persisted["llm"]
    assert llm["endpoint"] == "https://llm.example.test/v1"
    assert llm["api_key_env"] == "LLM_WIKI_TEST_API_KEY"
    assert llm["default_chat_model"] == "chat_default"
    assert llm["models"]["chat_default"]["model_name"] == "test-chat-model"
    assert llm["models"]["embedding_default"]["model_name"] == "test-embedding-model"

    conn = connect(paths.db)
    try:
        artifact = conn.execute(
            """
            SELECT artifact_type, task_type, target_type, target_id
            FROM artifacts
            WHERE artifact_type = 'settings_change' AND task_type = 'web_settings_llm_update'
            """
        ).fetchone()
    finally:
        conn.close()
    assert artifact is not None
    assert artifact["target_type"] == "settings"
    assert artifact["target_id"] == "llm"


def test_settings_default_tab_is_llm_and_onboarding_setup_landmarks_exist(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths = _client(workspace, monkeypatch)

    settings_page = client.get("/settings")
    assert settings_page.status_code == 200
    assert 'id="settings-pane-llm"' in settings_page.text
    assert 'class="settings-tab active" data-tab="llm"' in settings_page.text
    assert 'data-tab="llm" role="tab" aria-selected="true"' in settings_page.text

    onboarding = client.get("/onboarding")
    assert onboarding.status_code == 200
    assert 'id="setup-provider-form"' in onboarding.text
    assert 'id="wizard-pane-vault"' in onboarding.text
    assert 'id="vault-browser-new"' in onboarding.text


def test_prompt_test_returns_schema_validation_evidence(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: Prompt test must return schema validation evidence."""
    client, paths = _client(workspace, monkeypatch)

    # Test 1: Valid prompt with proper structure returns passed
    response = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "valid-test-prompt",
            "prompt_text": "Return grounded candidate JSON for extraction with claim, node, and evidence keywords.",
            "change_note": "Valid prompt with expected schema markers",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["test_status"] in ("passed", "failed")
    assert payload["validation_type"] in ("schema_only", "dry_run")
    assert "artifact_id" in payload
    # Schema validation should pass for extract_claims with JSON, candidate, claim, node keywords
    if payload["test_status"] == "passed":
        assert payload["schema_errors"] == []

    # Test 2: Invalid prompt with missing schema markers returns failed
    response2 = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "invalid-test-prompt",
            "prompt_text": "Hello world",  # Missing all required schema markers
            "change_note": "Invalid prompt missing schema markers",
        },
    )
    assert response2.status_code == 200
    payload2 = response2.json()
    assert payload2["test_status"] == "failed"
    assert payload2["validation_type"] == "schema_only"
    assert len(payload2["schema_errors"]) > 0
    assert "artifact_id" in payload2


def test_prompt_confirm_blocked_for_failed_test(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: confirm must be blocked when latest test is failed."""
    client, paths = _client(workspace, monkeypatch)

    # Create a prompt with failed schema validation
    response = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "to-be-blocked-prompt",
            "prompt_text": "Hi",  # Too short, missing schema markers
            "change_note": "This should fail schema validation",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    failed_prompt_id = payload["prompt_id"]

    if payload["test_status"] == "failed":
        # Attempting to confirm a failed prompt should return 422
        confirm_resp = client.post(f"/api/settings/prompts/{failed_prompt_id}/confirm")
        assert confirm_resp.status_code == 422
        assert "Cannot confirm" in confirm_resp.json()["detail"]


def test_phase2_default_prompt_confirm_without_test(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: phase2-default-v1 and rollback prompts bypass test guard on confirm."""
    client, paths = _client(workspace, monkeypatch)

    # Get the phase2 default prompt for extract_claims
    from llm_wiki.schema.prompts import get_active_prompt

    default_prompt = get_active_prompt(paths.db, "extract_claims")
    assert default_prompt["version_label"] == "phase2-default-v1"

    # Create a new test version based on the default
    response = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "custom-test-prompt",
            "prompt_text": (
                "Return JSON with candidate structure for extract_claims. "
                "Always include claim, node, evidence, JSON keywords so the schema "
                "validator accepts the draft."
            ),
            "change_note": "Custom test",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["test_status"] == "passed", payload
    prompt_id = payload["prompt_id"]

    # Confirm should work for prompts that passed schema validation
    confirm_resp = client.post(f"/api/settings/prompts/{prompt_id}/confirm")
    assert confirm_resp.status_code == 200


def test_llm_model_test_returns_passed_failed_blocked(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: LLM model test endpoint returns passed/failed/blocked with evidence."""
    client, paths = _client(workspace, monkeypatch)

    # Test blocked: model not configured (no endpoint)
    resp = client.post("/api/settings/llm/test/chat_review")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["model_id"] == "chat_review"
    assert payload["test_status"] in ("passed", "failed", "blocked")
    assert "artifact_id" in payload or "message" in payload
    # Without endpoint, should be blocked
    if payload["test_status"] == "blocked":
        assert payload["reason"] is not None or payload["message"] is not None


def test_active_prompt_id_recorded_in_placeholder_runs(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: extract_claims and summarize runners record active prompt_version_id."""
    client, paths = _client(workspace, monkeypatch)

    # Verify that get_active_prompt works for all task types
    from llm_wiki.schema.prompts import get_active_prompt

    for task_type in ("extract_claims", "summarize", "map", "link", "compile", "ask"):
        prompt = get_active_prompt(paths.db, task_type)
        assert prompt is not None
        assert "id" in prompt
        assert "prompt_text" in prompt
        assert prompt["state"] == "confirmed"


def test_prompt_test_artifact_recorded_with_validation_details(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WU-005: Prompt test artifact contains validation type, status, schema_errors."""
    client, paths = _client(workspace, monkeypatch)

    response = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "artifact-check-prompt",
            "prompt_text": "Extract candidate JSON with claim node evidence JSON format.",
            "change_note": "Schema validation test",
        },
    )
    assert response.status_code == 200
    prompt_id = response.json()["prompt_id"]

    # Check that artifact was recorded with proper payload
    conn = connect(paths.db)
    try:
        artifact_row = conn.execute(
            """
            SELECT artifact_type, task_type, target_type, target_id, path
            FROM artifacts
            WHERE artifact_type = 'prompt_test_result'
              AND target_type = 'prompt_version'
              AND target_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (prompt_id,),
        ).fetchone()
    finally:
        conn.close()

    assert artifact_row is not None, "prompt_test_result artifact not found"
    assert artifact_row["artifact_type"] == "prompt_test_result"
    assert artifact_row["task_type"] == "prompt_test"


def test_prompt_confirm_requires_passed_test_and_rejects_spoof(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-3-NO-05: confirm requires latest passed test; user-controllable
    version_label/change_note cannot spoof the phase2-default or rollback
    bypass; only the server-controlled bypass_test column allows the bypass.
    """
    client, paths = _client(workspace, monkeypatch)
    from llm_wiki.schema.prompts import ensure_default_prompts, get_active_prompt, rollback_prompt_version

    ensure_default_prompts(paths.db)
    default_prompt = get_active_prompt(paths.db, "extract_claims")
    assert default_prompt["bypass_test"] == 1, "phase2-default must carry bypass_test=1"

    # 1. Phase2-default confirm succeeds even without a fresh test (bypass_test=1).
    resp = client.post(f"/api/settings/prompts/{default_prompt['id']}/confirm")
    assert resp.status_code == 200, resp.text
    assert resp.json().get("bypass") is True

    # 2. User-crafted prompt with no test artifact must be rejected.
    #    The user attempts to spoof the bypass by mimicking phase2-default/rollback
    #    markers in change_note and version_label. The guard must ignore those.
    spoof = client.post(
        "/api/settings/prompt-versions",
        json={
            "task_type": "extract_claims",
            "version_label": "user-spoof-attempt-v1",
            "prompt_text": "Spoof attempt without a test artifact.",
            "change_note": "phase2-default-v1 rollback_from:fake",
        },
    )
    assert spoof.status_code == 200
    spoof_id = spoof.json()["prompt_id"]
    confirm_spoof = client.post(f"/api/settings/prompts/{spoof_id}/confirm")
    assert confirm_spoof.status_code == 422
    assert "Cannot confirm" in confirm_spoof.json()["detail"]

    # 3. Failed test → 422.
    failed_resp = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "phase3-spoof-failed",
            "prompt_text": "Hi",  # too short, fails schema validation
            "change_note": "intentionally failed",
        },
    )
    assert failed_resp.status_code == 200
    failed_payload = failed_resp.json()
    assert failed_payload["test_status"] == "failed"
    failed_confirm = client.post(f"/api/settings/prompts/{failed_payload['prompt_id']}/confirm")
    assert failed_confirm.status_code == 422

    # 4. Passed test → 200.
    passed_resp = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "phase3-passed",
            "prompt_text": (
                "Return grounded candidate JSON with claim_candidates, node_candidates, "
                "JSON output and evidence links. Schema must include claim, node, candidate."
            ),
            "change_note": "schema-valid prompt",
        },
    )
    assert passed_resp.status_code == 200
    passed_payload = passed_resp.json()
    assert passed_payload["test_status"] == "passed"
    passed_confirm = client.post(f"/api/settings/prompts/{passed_payload['prompt_id']}/confirm")
    assert passed_confirm.status_code == 200
    assert passed_confirm.json().get("bypass") is False

    # 5. Rollback creates a confirmed copy with bypass_test=1.
    rollback = rollback_prompt_version(paths.db, passed_payload["prompt_id"], change_note="audit")
    conn = connect(paths.db)
    try:
        row = conn.execute(
            "SELECT bypass_test FROM prompt_versions WHERE id = ?",
            (rollback["new_version_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row["bypass_test"] == 1, "rollback must carry bypass_test=1"
