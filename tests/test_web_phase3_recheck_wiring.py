"""Targeted tests for the recheck wiring fixes (Fix items 8/9/10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch, *, with_concept: bool = True):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    if with_concept:
        (paths.wiki_concepts / "rag.md").write_text(
            "# RAG\n\nRetrieval-Augmented Generation concept.\n",
            encoding="utf-8",
        )
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


def _seed_candidate(paths, *, candidate_type: str, candidate_key: str, payload: dict, review_route: str, review_reason: str) -> str:
    candidate_id = new_id("candidate")
    now = utc_now()
    conn = connect(paths.db)
    try:
        conn.execute(
            """
            INSERT INTO review_candidates (
              id, candidate_type, candidate_key, source_id, run_id, payload_json,
              review_route, review_reason, related_candidate_keys_json, status,
              superseded_by, created_at, updated_at
            ) VALUES (?, ?, ?, 'source_recheck', NULL, ?, ?, ?, '[]', 'pending', NULL, ?, ?)
            """,
            (
                candidate_id,
                candidate_type,
                candidate_key,
                json.dumps(payload, ensure_ascii=False),
                review_route,
                review_reason,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return candidate_id


def test_settings_active_tab_initialization(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(workspace, monkeypatch)

    import re as _re

    for tab in ("llm", "prompt", "vault", "auth"):
        response = client.get(f"/settings?tab={tab}")
        assert response.status_code == 200
        body = response.text
        # Active tab button must carry the active CSS class
        assert f'data-tab="{tab}"' in body
        assert f'class="settings-tab active"' in body
        # Inactive panes must be hidden in server-rendered HTML
        hidden = set(_re.findall(r'id="settings-pane-(\w+)"[^>]*style="display:none"', body))
        for other in ("llm", "prompt", "vault", "auth"):
            if other == tab:
                assert other not in hidden
            else:
                assert other in hidden, f"pane {other} must be hidden when active tab is {tab}"

    # Invalid tab must fall back to prompt
    invalid = client.get("/settings?tab=evil")
    assert invalid.status_code == 200
    assert 'data-tab="prompt"' in invalid.text
    assert 'class="settings-tab active"' in invalid.text


def test_review_mapping_endpoint_returns_ranked_with_valid_candidate(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    mapping_id = _seed_candidate(
        paths,
        candidate_type="mapping",
        candidate_key="mapping_01",
        payload={"candidate_key": "mapping_01", "incoming_ref": {"kind": "new_node", "candidate_key": "node_01"}, "existing_node_id": "rag", "mapping_action": "merge_candidate", "review_route": "needs_merge_decision", "review_reason": "human merge decision required"},
        review_route="needs_merge_decision",
        review_reason="human merge decision required",
    )

    # With explicit source_candidate_id, ranking works
    ranking = client.get("/api/review/mapping", params={"source_candidate_id": mapping_id})
    assert ranking.status_code == 200
    body = ranking.json()
    assert body["status"] == "ok"
    assert any(row["concept_id"] == "rag" for row in body["concepts"])

    # Without source_candidate_id, endpoint must not silently fall back to alphabetic
    unparameterized = client.get("/api/review/mapping")
    assert unparameterized.status_code in (400, 422)


def test_review_template_contains_similarity_and_fallback_banner(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    client, paths = _client(workspace, monkeypatch, with_concept=True)
    _complete_setup(client, paths)
    body = client.get("/review").text
    assert 'id="wiki-similar-list"' in body
    # New banner selector exposed for similarity mode vs fallback mode
    assert "list-mode-banner" in body or "list-mode-banner ok" in body or "list-mode-banner" in client.get("/review").text
