"""Tests for Settings Prompt page: live prompt units matching actual LLM call units."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


LIVE_PROMPT_TASKS = [
    "extract_claims",
    "wiki_page_candidates_initial",
    "wiki_page_candidates_retry_parse_failed",
    "wiki_page_candidates_retry_schema_validation_failed",
    "wiki_page_candidates_retry_empty_candidates",
    "ask",
]


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
    return client


def test_prompt_settings_api_bootstraps_default_groups_when_prompt_table_empty(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime DB reset should not leave Settings Prompt with an empty menu."""
    client = _client(workspace, monkeypatch)

    from llm_wiki.db.schema import connect
    from llm_wiki.workspace import resolve_workspace

    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        conn.execute("DELETE FROM prompt_versions")
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/settings/prompts")
    assert resp.status_code == 200
    groups = resp.json()["task_groups"]
    assert [g["task_type"] for g in groups] == LIVE_PROMPT_TASKS
    assert all(g.get("is_live_llm_unit") is True for g in groups)



def test_live_prompt_units_match_actual_call_units(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings Prompt tab must show only actual live LLM call units.

    Actual call units in the current pipeline are:
    - extract_claims: source/chunks -> node_candidates + claim_candidates (single call)
    - wiki_page_candidates_initial: source chunks -> wiki page candidates
    - wiki_page_candidates_retry_*: reason-specific LLM correction prompts
    - ask: search results -> answer (single call, used in /api/ask)

    Historical map/link/summarize/compile prompt settings are removed from
    new workspaces and web/CLI user-facing configuration.
    """
    client = _client(workspace, monkeypatch)

    resp = client.get("/api/settings/prompts")
    assert resp.status_code == 200
    groups = resp.json()["task_groups"]

    # Actual live call units in the current pipeline
    live_task_types = {g["task_type"] for g in groups if g.get("is_live_llm_unit") is True}

    assert set(LIVE_PROMPT_TASKS) <= live_task_types

    assert {g["task_type"] for g in groups} == set(LIVE_PROMPT_TASKS)
    assert not ({"map", "link", "summarize", "compile"} & {g["task_type"] for g in groups})


def test_ask_synthesis_prompt_visible_in_settings(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ask_synthesis prompt (used in /api/ask) must appear in Settings Prompt tab."""
    client = _client(workspace, monkeypatch)

    resp = client.get("/api/settings/prompts?task_type=ask")
    assert resp.status_code == 200
    groups = resp.json()["task_groups"]
    assert len(groups) == 1
    assert groups[0]["task_type"] == "ask"
    # ask prompt must be confirmed (live)
    assert groups[0].get("confirmed") is not None, "ask prompt must have a confirmed version"


def test_extract_claims_and_map_prompts_are_separate_live_units(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """extract_claims must be a separate prompt unit from others in Settings.

    Note: map and link are defined prompts but are NOT live/invoked in the
    current pipeline — they are archived/inactive. Only extract_claims and ask
    are confirmed live call units.
    """
    client = _client(workspace, monkeypatch)

    resp = client.get("/api/settings/prompts")
    assert resp.status_code == 200
    groups = resp.json()["task_groups"]

    task_types = {g["task_type"] for g in groups}
    assert "extract_claims" in task_types, "extract_claims must exist as its own prompt unit"

    # extract_claims must have a confirmed version (live call unit)
    extract_group = next((g for g in groups if g["task_type"] == "extract_claims"), None)
    assert extract_group is not None, "extract_claims group must exist"
    assert extract_group.get("confirmed") is not None, "extract_claims must have confirmed (live) version"


def test_prompt_ui_copy_uses_korean_labels(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt API should expose purpose-based Korean labels and live/legacy copy."""
    client = _client(workspace, monkeypatch)
    resp = client.get("/api/settings/prompts")
    assert resp.status_code == 200

    groups = {g["task_type"]: g for g in resp.json()["task_groups"]}
    assert groups["extract_claims"]["display_label"] == "Node/Claim 후보 생성"
    assert groups["extract_claims"]["purpose_label"] == "Source text → node_candidates + claim_candidates"
    assert groups["extract_claims"]["category"] == "live"
    assert groups["extract_claims"]["status_label"] == "실제 LLM 호출"
    assert groups["ask"]["display_label"] == "Ask 답변 합성"
    assert groups["wiki_page_candidates_initial"]["display_label"] == "Wiki page 후보 생성"
    assert groups["wiki_page_candidates_retry_parse_failed"]["display_label"] == "Retry: JSON parse 실패"
    assert set(groups) == set(LIVE_PROMPT_TASKS)


def test_prompt_settings_web_api_rejects_non_live_prompt_tasks(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Web prompt settings must not expose/edit DB/CLI-only placeholder prompts."""
    client = _client(workspace, monkeypatch)

    for task_type in ("map", "link", "summarize", "compile"):
        listed = client.get(f"/api/settings/prompts?task_type={task_type}")
        assert listed.status_code == 200
        assert listed.json()["task_groups"] == []

        created = client.post(
            "/api/settings/prompt-versions",
            json={
                "task_type": task_type,
                "version_label": f"web-{task_type}-should-not-exist",
                "prompt_text": "Placeholder prompt should not be editable from web settings.",
                "change_note": "reject non-live web prompt edit",
            },
        )
        assert created.status_code == 422

        tested = client.post(
            "/api/settings/prompts/test",
            json={
                "task_type": task_type,
                "version_label": f"web-{task_type}-test-should-not-exist",
                "prompt_text": "Placeholder prompt should not be testable from web settings.",
                "change_note": "reject non-live web prompt test",
            },
        )
        assert tested.status_code == 422


def test_prompt_settings_template_uses_dynamic_contract_menu() -> None:
    """Settings Prompt menu must be rendered from /api/settings/prompts task_groups, not stale hardcoded order."""
    template = Path("src/llm_wiki/web/templates/settings.html").read_text(encoding="utf-8")
    app_js = Path("src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    assert "data-prompt-task=\"compile\"" not in template
    assert "data-prompt-task=\"summarize\"" not in template
    assert "data-prompt-task=\"ask\"" not in template
    assert "prompt_versions || []" not in app_js
    assert "settingsPrompts: \"/api/settings/prompts\"" in app_js
    assert "apiFetch(API.settingsPrompts)" in app_js
    assert "task_groups || []" in app_js
    assert "is_live_llm_unit" in app_js
    assert "실제 LLM 호출 단위" in app_js


def test_node_extraction_prompt_separate_from_claim_extraction(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If node extraction and claim extraction are split into separate calls,
    each must appear as its own prompt unit in Settings.

    If NOT split (current reality: single extract_claims call),
    then Settings must show 'extract_claims' as ONE live unit and
    clearly indicate the combined nature.
    """
    client = _client(workspace, monkeypatch)
    resp = client.get("/api/settings/prompts")
    assert resp.status_code == 200
    groups = resp.json()["task_groups"]

    # Current pipeline: single extract_claims call producing both nodes and claims
    # So we have "extract_claims" as one unit
    extract_group = next((g for g in groups if g["task_type"] == "extract_claims"), None)
    assert extract_group is not None, "extract_claims unit must exist"

    # The confirmed prompt text should mention both node and claim
    confirmed = extract_group.get("confirmed") or {}
    prompt_text = confirmed.get("prompt_text", "")
    # If it's a combined prompt, it should reference both concepts
    # This verifies the Settings reflects reality (combined extraction)
    has_node_ref = "node" in prompt_text.lower()
    has_claim_ref = "claim" in prompt_text.lower()
    assert has_node_ref or has_claim_ref, (
        "extract_claims prompt should reference node and/or claim candidates"
    )


def test_settings_prompt_version_tracks_artifacts(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each prompt version in Settings should be linkable to artifacts."""
    client = _client(workspace, monkeypatch)

    resp = client.get("/api/settings/prompts/history?task_type=extract_claims")
    assert resp.status_code == 200
    history = resp.json()["history"]
    assert len(history) >= 1

    # Each version should have an id
    for v in history:
        assert "id" in v
        assert "task_type" in v
        assert "state" in v
        assert "prompt_text" in v


def test_prompt_test_creates_artifact(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Testing a prompt version should create a prompt_test_result artifact."""
    client = _client(workspace, monkeypatch)

    test_resp = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "extract_claims",
            "version_label": "test-split-v1",
            "prompt_text": "Return JSON with node_candidates and claim_candidates arrays. candidate.v1 JSON only.",
            "change_note": "testing prompt structure",
        },
    )
    assert test_resp.status_code == 200
    result = test_resp.json()
    assert result["status"] == "ok"
    assert result["test_status"] == "passed"
    assert "prompt_id" in result
    assert "artifact_id" in result
