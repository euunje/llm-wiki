from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.schema.prompts import create_prompt_version
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("LLM_WIKI_API_KEY", "phase3-test-api-key")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def _insert_candidate(
    db_path: Path,
    *,
    candidate_type: str,
    candidate_key: str,
    payload: dict[str, object],
    review_route: str,
    review_reason: str,
) -> str:
    candidate_id = new_id("candidate")
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO review_candidates (
              id, candidate_type, candidate_key, source_id, run_id, payload_json,
              review_route, review_reason, related_candidate_keys_json, status,
              superseded_by, created_at, updated_at
            ) VALUES (?, ?, ?, 'source_phase3', NULL, ?, ?, ?, ?, 'pending', NULL, ?, ?)
            """,
            (
                candidate_id,
                candidate_type,
                candidate_key,
                json.dumps(payload, ensure_ascii=False),
                review_route,
                review_reason,
                json.dumps(payload.get("related_candidate_keys", []), ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return candidate_id


def _seed_complete_workspace(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    client, paths = _client(workspace, monkeypatch)
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
    (paths.wiki_concepts / "rag.md").write_text(
        """# Retrieval-Augmented Generation

## Aliases
- RAG
- Grounded generation

## Meaning
Retrieval-Augmented Generation grounds an answer in retrieved evidence.

## Claims
- Retrieved evidence improves answer traceability.

## Relations
- related_to: [[Vector Search]]
""",
        encoding="utf-8",
    )
    (paths.wiki_concepts / "vector-search.md").write_text(
        """# Vector Search

## Aliases
- Similarity search

## Meaning
Vector Search finds semantically similar records.

## Claims
- Embeddings support semantic retrieval.

## Relations
- supports: [[Retrieval-Augmented Generation]]
""",
        encoding="utf-8",
    )

    node_payload = {
        "candidate_key": "node_01",
        "node_type": "concept",
        "title": "Candidate Only Concept",
        "aliases": ["Candidate fallback"],
        "summary": "This candidate intentionally has no concept markdown file.",
        "evidence_claim_keys": ["claim_01"],
        "review_route": "normal_review",
        "review_reason": "new concept needs review",
        "related_candidate_keys": ["mapping_01", "relation_01"],
    }
    mapping_payload = {
        "candidate_key": "mapping_01",
        "incoming_ref": {"kind": "new_node", "candidate_key": "node_01"},
        "existing_node_id": "rag",
        "mapping_action": "merge_candidate",
        "evidence_claim_keys": ["claim_01"],
        "reason": "The candidate overlaps the seeded RAG concept.",
        "review_route": "needs_merge_decision",
        "review_reason": "human merge decision required",
        "related_candidate_keys": ["node_01"],
        "model_confidence": 0.88,
    }
    relation_payload = {
        "candidate_key": "relation_01",
        "source_ref": {"kind": "new_node", "candidate_key": "node_01"},
        "relation_type": "related_to",
        "target_ref": {"kind": "existing_node", "id": "vector-search"},
        "evidence_claim_keys": ["claim_01"],
        "review_route": "normal_review",
        "review_reason": "relation needs review",
        "related_candidate_keys": ["node_01"],
        "model_confidence": 0.74,
    }
    _insert_candidate(
        paths.db,
        candidate_type="mapping",
        candidate_key="mapping_01",
        payload=mapping_payload,
        review_route="needs_merge_decision",
        review_reason="human merge decision required",
    )
    _insert_candidate(
        paths.db,
        candidate_type="node",
        candidate_key="node_01",
        payload=node_payload,
        review_route="normal_review",
        review_reason="new concept needs review",
    )
    _insert_candidate(
        paths.db,
        candidate_type="relation",
        candidate_key="relation_01",
        payload=relation_payload,
        review_route="normal_review",
        review_reason="relation needs review",
    )
    create_prompt_version(
        paths.db,
        "phase3_seed",
        "phase3-seed-test-v1",
        "Seeded test prompt",
        state="test",
        change_note="Phase 3 functional seed",
    )
    create_prompt_version(
        paths.db,
        "phase3_seed",
        "phase3-seed-confirmed-v1",
        "Seeded confirmed prompt",
        state="confirmed",
        change_note="Phase 3 functional seed",
    )
    return client, paths, mapping_payload


def test_setup_status_and_wiki_apis_return_seeded_workspace(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths, _mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    setup = client.get("/api/setup/status")
    assert setup.status_code == 200
    setup_payload = setup.json()
    assert {
        "status",
        "workspace_initialized",
        "needs_onboarding",
        "setup_complete",
        "db_exists",
        "db_schema_ok",
        "web_admin_password_configured",
        "llm",
        "components",
        "counts",
        "next_actions",
    } <= set(setup_payload)
    assert setup_payload["status"] == "ok"
    assert setup_payload["workspace_initialized"] is True
    assert setup_payload["needs_onboarding"] is False
    assert setup_payload["setup_complete"] is True
    assert setup_payload["db_exists"] is True
    assert setup_payload["db_schema_ok"] is True
    assert setup_payload["web_admin_password_configured"] is True
    assert {
        "endpoint_configured",
        "chat_model_configured",
        "embedding_model_configured",
        "api_key_configured",
        "connection_status",
        "status",
    } <= set(setup_payload["llm"])
    assert setup_payload["llm"]["status"] == "ready"
    assert setup_payload["components"]["vault"]["status"] == "ready"
    assert setup_payload["components"]["llm_connection"]["status"] == "ready"
    assert setup_payload["counts"]["wiki_concepts"] == 2
    assert setup_payload["counts"]["review_candidates"]["pending"] == 3

    pages = client.get("/api/wiki/pages")
    assert pages.status_code == 200
    pages_payload = pages.json()
    assert pages_payload["count"] == 2
    assert {page["id"] for page in pages_payload["pages"]} == {"rag", "vector-search"}

    detail = client.get("/api/wiki/pages/rag")
    assert detail.status_code == 200
    page = detail.json()["page"]
    assert "Retrieval-Augmented Generation grounds" in page["content"]
    assert "RAG" in page["aliases"]
    assert any("traceability" in claim for claim in page["claims"])
    assert any("Vector Search" in json.dumps(relation, ensure_ascii=False) for relation in page["relations"])


def test_mapping_api_returns_seeded_candidate_payload(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths, mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    # The mapping endpoint expects a source candidate id and returns a similarity-ranked
    # concept list for that candidate. Use the seeded mapping candidate's id.
    mapping_candidate_id = next(
        row["id"]
        for row in connect(paths.db).execute(
            "SELECT id, candidate_key FROM review_candidates WHERE candidate_key = ?",
            ("mapping_01",),
        ).fetchall()
    )
    mapping = client.get("/api/review/mapping", params={"source_candidate_id": mapping_candidate_id})
    assert mapping.status_code == 200
    body = mapping.json()
    assert body["status"] == "ok"
    assert body["count"] >= 1
    # The seeded RAG concept must appear in the similarity-ranked concept list.
    concept_ids = {row["concept_id"] for row in body["concepts"]}
    assert "rag" in concept_ids
    rag_row = next(row for row in body["concepts"] if row["concept_id"] == "rag")
    assert rag_row["title"]
    # The mapping payload itself is verified via the candidate detail endpoint.
    candidate = client.get(f"/api/review/candidates/{mapping_candidate_id}")
    assert candidate.status_code == 200
    candidate_payload = candidate.json()["candidate"]["payload"]
    assert candidate_payload["mapping_action"] == mapping_payload["mapping_action"]
    assert candidate_payload["existing_node_id"] == "rag"
    assert candidate_payload["model_confidence"] == 0.88


def test_graph_falls_back_to_candidate_without_concept_markdown(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths, _mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    graph = client.get("/api/review/graph/node_01")
    assert graph.status_code == 200
    graph_payload = graph.json()["graph"]
    assert graph_payload["center"]["id"] == "node_01"
    assert graph_payload["center"]["kind"] == "candidate"
    assert "Candidate Only Concept" in json.dumps(graph_payload, ensure_ascii=False)


def test_onboarding_page_contains_checklist_elements(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths, _mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    onboarding = client.get("/onboarding", follow_redirects=False)
    assert onboarding.status_code == 303
    assert onboarding.headers["location"] == "/dashboard"


def test_completed_setup_hides_onboarding_nav_and_routes_root_to_dashboard(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths, _mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    root = client.get("/", follow_redirects=False)
    dashboard = client.get("/dashboard")

    assert root.status_code == 303
    assert root.headers["location"] == "/dashboard"
    assert dashboard.status_code == 200
    assert 'aria-label="Onboarding"' not in dashboard.text
    assert '>🔌 Onboarding<' not in dashboard.text


def test_wiki_page_contains_list_container(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths, _mapping_payload = _seed_complete_workspace(workspace, monkeypatch)

    wiki = client.get("/wiki")
    assert wiki.status_code == 200
    assert 'id="wiki-page-list"' in wiki.text


def test_setup_complete_requires_passed_llm_connection_test(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-3-NO-01: setup_complete=true requires llm_connection.test_status == 'passed'.

    Saved endpoint+key without models MUST NOT yield setup_complete=true.
    Saved models without a passing test MUST NOT yield setup_complete=true.
    Updating endpoint alone MUST preserve existing model selections.
    """
    client, paths = _client(workspace, monkeypatch)

    # (a) Saved endpoint+key without models → setup_complete=false
    cfg = client.post(
        "/api/settings/llm/config",
        json={"endpoint": "http://localhost:11434", "api_key_env": "LLM_WIKI_API_KEY"},
    )
    assert cfg.status_code == 200
    s = client.get("/api/setup/status").json()
    assert s["setup_complete"] is False
    assert s["components"]["llm_connection"]["test_status"] in {"blocked", "failed"}

    # (b) Saved models without a passing connection test → setup_complete=false
    cfg2 = client.post(
        "/api/settings/llm/config",
        json={
            "endpoint": "http://localhost:11434",
            "api_key_env": "LLM_WIKI_API_KEY",
            "chat_model_name": "gpt-4",
            "embedding_model_name": "text-embedding-ada-002",
        },
    )
    assert cfg2.status_code == 200
    s = client.get("/api/setup/status").json()
    assert s["setup_complete"] is False
    assert s["llm"]["chat_model"] == "gpt-4"
    assert s["llm"]["embedding_model"] == "text-embedding-ada-002"
    # Without a successful test, llm_connection is still blocked.
    assert s["components"]["llm_connection"]["test_status"] in {"blocked", "failed"}

    # (d) Updating endpoint alone preserves existing model selections.
    cfg3 = client.post(
        "/api/settings/llm/config",
        json={"endpoint": "http://localhost:11435", "api_key_env": "LLM_WIKI_API_KEY"},
    )
    assert cfg3.status_code == 200
    s = client.get("/api/setup/status").json()
    assert s["llm"]["chat_model"] == "gpt-4", "chat model must survive endpoint-only update"
    assert s["llm"]["embedding_model"] == "text-embedding-ada-002", "embedding must survive endpoint-only update"
