from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect
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


def test_review_apis_list_candidates_show_concepts_and_record_decisions(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nCore retrieval concept.\n", encoding="utf-8")
    candidate_id = new_id("candidate")
    now = utc_now()

    conn = connect(paths.db)
    try:
        payload = {
            "candidate_key": "mapping_01",
            "incoming_ref": {"kind": "new_node", "candidate_key": "node_01"},
            "existing_node_id": "rag",
            "mapping_action": "merge_candidate",
            "evidence_claim_keys": ["claim_01"],
            "reason": "similar",
            "review_route": "needs_merge_decision",
            "review_reason": "merge needed",
            "related_candidate_keys": ["node_01"],
            "model_confidence": 0.8,
        }
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'mapping', 'mapping_01', 'source_x', NULL, ?, 'needs_merge_decision', 'merge needed', '[\"node_01\"]', 'pending', NULL, ?, ?)",
            (candidate_id, json.dumps(payload, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    candidates = client.get("/api/review/candidates")
    assert candidates.status_code == 200
    assert candidates.json()["count"] == 1

    concepts = client.get("/api/review/concepts")
    assert concepts.status_code == 200
    assert concepts.json()["concepts"][0]["id"] == "rag"

    detail = client.get("/api/review/concepts/rag")
    assert detail.status_code == 200
    assert "Core retrieval concept" in detail.json()["concept"]["content"]

    wiki_list = client.get("/api/wiki/pages?query=rag")
    assert wiki_list.status_code == 200
    assert wiki_list.json()["pages"][0]["id"] == "rag"

    wiki_detail = client.get("/api/wiki/pages/rag")
    assert wiki_detail.status_code == 200
    assert wiki_detail.json()["page"]["title"] == "RAG"

    graph = client.get("/api/review/graph/rag")
    assert graph.status_code == 200
    assert graph.json()["graph"]["center"]["id"] == "rag"
    assert graph.json()["graph"]["edges"][0]["target"] == "rag"

    mapping = client.get(f"/api/review/mapping?source_candidate_id={candidate_id}")
    assert mapping.status_code == 200
    assert mapping.json()["concepts"][0]["concept_id"] == "rag"

    candidate_detail = client.get(f"/api/review/candidates/{candidate_id}")
    assert candidate_detail.status_code == 200
    assert candidate_detail.json()["candidate"]["source"]["id"] == "source_x"

    batch = client.post("/api/review/decide", json={"action": "batch_select", "candidate_ids": [candidate_id]})
    assert batch.status_code == 200
    assert batch.json()["selected_count"] == 1

    decision = client.post("/api/review/decide", json={"candidate_id": candidate_id, "action": "merge", "note": "merge into RAG"})
    assert decision.status_code == 200
    assert decision.json()["action"] == "merge"

    retry_candidate_id = new_id("candidate")
    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'node_02', 'source_x', NULL, '{}', 'needs_retry', 'retry', '[]', 'pending', NULL, ?, ?)",
            (retry_candidate_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    retry = client.post(
        "/api/review/decide",
        json={
            "candidate_id": retry_candidate_id,
            "action": "retry_with_instruction",
            "reason": "too broad",
            "instruction": "narrow the concept",
        },
    )
    assert retry.status_code == 200
    assert retry.json()["retry_instruction_id"]

    conn = connect(paths.db)
    try:
        status_row = conn.execute("SELECT status FROM review_candidates WHERE id = ?", (retry_candidate_id,)).fetchone()
        retry_row = conn.execute("SELECT reason, instruction FROM retry_instructions WHERE target_candidate_id = ?", (retry_candidate_id,)).fetchone()
    finally:
        conn.close()
    assert status_row[0] == "retry_requested"
    assert retry_row[0] == "too broad"
    assert retry_row[1] == "narrow the concept"


def test_review_graph_and_concept_detail_fallback_to_candidate(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    candidate_id = new_id("candidate")
    now = utc_now()
    payload = {"candidate_key": "candidate_only", "title": "Candidate Only", "summary": "fallback detail"}

    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'candidate_only', NULL, NULL, ?, 'normal_review', '', '[]', 'pending', NULL, ?, ?)",
            (candidate_id, json.dumps(payload, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    graph = client.get("/api/review/graph/candidate_only")
    assert graph.status_code == 200
    assert graph.json()["graph"]["reason"] == "candidate_fallback"

    detail = client.get("/api/review/concepts/candidate_only")
    assert detail.status_code == 200
    assert "fallback detail" in detail.json()["concept"]["content"]


def test_grouped_review_suggestions_groups_claims_under_node(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    now = utc_now()
    source_id = "source_grouped_01"
    node_id = new_id("candidate")
    claim_1_id = new_id("candidate")
    claim_2_id = new_id("candidate")
    mapping_id = new_id("candidate")

    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO sources (id, source_type, title, origin, raw_path, normalized_path, content_hash, pipeline_stage, review_status, metadata_json, created_at, updated_at) VALUES (?, 'text', 'Grouped Source', 'test', 'data/raw/grouped-source.md', NULL, ?, 'candidate_generated', 'needs_mapping', ?, ?, ?)",
            (source_id, f"hash-{source_id}", json.dumps({"original_filename": "Grouped Source Original.md"}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'node_01', ?, NULL, ?, 'normal_review', 'node review', '[\"claim_01\"]', 'pending', NULL, ?, ?)",
            (node_id, source_id, json.dumps({"candidate_key": "node_01", "title": "Node 01", "summary": "Grouped node", "node_type": "concept", "evidence_claim_keys": ["claim_01"], "extraction_model_id": "chat_default", "extraction_model_name": "google/gemma-4-26b-a4b-qat"}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'claim', 'claim_01', ?, NULL, ?, 'normal_review', 'claim attached', '[\"node_01\"]', 'pending', NULL, ?, ?)",
            (claim_1_id, source_id, json.dumps({"candidate_key": "claim_01", "statement": "Attached claim", "evidence": [{"quote": "claim one evidence"}]}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'claim', 'claim_02', ?, NULL, ?, 'normal_review', 'claim orphan', '[]', 'pending', NULL, ?, ?)",
            (claim_2_id, source_id, json.dumps({"candidate_key": "claim_02", "statement": "Orphan claim", "evidence": [{"quote": "claim two evidence"}]}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'mapping', 'mapping_01', ?, NULL, ?, 'needs_merge_decision', 'mapping attached', '[\"node_01\"]', 'pending', NULL, ?, ?)",
            (mapping_id, source_id, json.dumps({"candidate_key": "mapping_01", "existing_node_id": "rag", "reason": "similar", "incoming_ref": {"candidate_key": "node_01"}}, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/api/review/suggestions/grouped?source_id={source_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["node_group_count"] == 1
    assert payload["source"]["id"] == source_id
    assert payload["source"]["filename"] == "Grouped Source Original.md"
    group = payload["node_groups"][0]
    assert group["source"]["filename"] == "Grouped Source Original.md"
    assert group["model"]["model_id"] == "chat_default"
    assert group["model"]["model_name"] == "google/gemma-4-26b-a4b-qat"
    assert group["node_candidate"]["candidate_key"] == "node_01"
    assert [claim["candidate_key"] for claim in group["claims"]] == ["claim_01"]
    assert group["mapping_candidates"][0]["target_concept_id"] == "rag"
    assert payload["orphan_claims"][0]["candidate_key"] == "claim_02"
