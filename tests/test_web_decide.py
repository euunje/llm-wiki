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


def _seed_candidate(
    db_path: Path,
    *,
    candidate_type: str,
    candidate_key: str,
    payload: dict[str, object],
    review_route: str,
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
            ) VALUES (?, ?, ?, 'source_phase3', NULL, ?, ?, 'seeded functional test', '[]', 'pending', NULL, ?, ?)
            """,
            (
                candidate_id,
                candidate_type,
                candidate_key,
                json.dumps(payload, ensure_ascii=False),
                review_route,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return candidate_id


def test_decide_merge_and_retry_persist_candidate_and_human_state(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    merge_candidate_id = _seed_candidate(
        paths.db,
        candidate_type="mapping",
        candidate_key="mapping_decide_01",
        payload={
            "candidate_key": "mapping_decide_01",
            "incoming_ref": {"kind": "new_node", "candidate_key": "node_decide_01"},
            "existing_node_id": "rag",
            "mapping_action": "merge_candidate",
            "reason": "same concept",
        },
        review_route="needs_merge_decision",
    )
    retry_candidate_id = _seed_candidate(
        paths.db,
        candidate_type="node",
        candidate_key="node_retry_01",
        payload={
            "candidate_key": "node_retry_01",
            "title": "Overly Broad Candidate",
            "summary": "Needs narrower extraction.",
        },
        review_route="needs_retry",
    )

    merge = client.post(
        "/api/review/decide",
        json={
            "candidate_id": merge_candidate_id,
            "action": "merge",
            "note": "Merge into the existing RAG concept",
        },
    )
    assert merge.status_code == 200
    assert merge.json()["candidate_id"] == merge_candidate_id
    assert merge.json()["action"] == "merge"

    retry = client.post(
        "/api/review/decide",
        json={
            "candidate_id": retry_candidate_id,
            "action": "retry_with_instruction",
            "reason": "Candidate scope is too broad",
            "instruction": "Extract only the retrieval-specific concept",
        },
    )
    assert retry.status_code == 200
    retry_instruction_id = retry.json()["retry_instruction_id"]
    assert retry_instruction_id

    conn = connect(paths.db)
    try:
        merge_candidate = conn.execute(
            "SELECT status FROM review_candidates WHERE id = ?",
            (merge_candidate_id,),
        ).fetchone()
        merge_decision = conn.execute(
            "SELECT decision_type, note FROM human_decisions WHERE candidate_id = ?",
            (merge_candidate_id,),
        ).fetchone()
        retry_candidate = conn.execute(
            "SELECT status FROM review_candidates WHERE id = ?",
            (retry_candidate_id,),
        ).fetchone()
        retry_instruction = conn.execute(
            "SELECT id, reason, instruction FROM retry_instructions WHERE target_candidate_id = ?",
            (retry_candidate_id,),
        ).fetchone()
        retry_decision = conn.execute(
            "SELECT decision_type, retry_instruction_id FROM human_decisions WHERE candidate_id = ?",
            (retry_candidate_id,),
        ).fetchone()
    finally:
        conn.close()

    assert merge_candidate["status"] == "approved"
    assert merge_decision["decision_type"] == "merge"
    assert merge_decision["note"] == "Merge into the existing RAG concept"
    assert retry_candidate["status"] == "retry_requested"
    assert retry_instruction["id"] == retry_instruction_id
    assert retry_instruction["reason"] == "Candidate scope is too broad"
    assert retry_instruction["instruction"] == "Extract only the retrieval-specific concept"
    assert retry_decision["decision_type"] == "retry_with_instruction"
    assert retry_decision["retry_instruction_id"] == retry_instruction_id


def test_node_centric_decision_records_selected_claims(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    now = utc_now()
    source_id = "source_node_decide"
    node_candidate_id = new_id("candidate")
    claim_1_id = new_id("candidate")
    claim_2_id = new_id("candidate")

    conn = connect(paths.db)
    try:
        conn.execute(
            "INSERT INTO sources (id, source_type, title, origin, raw_path, normalized_path, content_hash, pipeline_stage, review_status, metadata_json, created_at, updated_at) VALUES (?, 'text', 'Decision Source', 'test', NULL, NULL, ?, 'candidate_generated', 'needs_mapping', '{}', ?, ?)",
            (source_id, f"hash-{source_id}", now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'node_decide_01', ?, NULL, ?, 'normal_review', 'seed node', '[\"claim_decide_01\", \"claim_decide_02\"]', 'pending', NULL, ?, ?)",
            (node_candidate_id, source_id, json.dumps({"candidate_key": "node_decide_01", "title": "Token Overhead", "body": "Token overhead is the extra prompt/context cost added by agent tools.", "tags": ["agent", "token-overhead"], "evidence_claim_keys": ["claim_decide_01", "claim_decide_02"]}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'claim', 'claim_decide_01', ?, NULL, ?, 'normal_review', 'claim one', '[\"node_decide_01\"]', 'pending', NULL, ?, ?)",
            (claim_1_id, source_id, json.dumps({"candidate_key": "claim_decide_01", "statement": "Claim one"}, ensure_ascii=False), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'claim', 'claim_decide_02', ?, NULL, ?, 'normal_review', 'claim two', '[\"node_decide_01\"]', 'pending', NULL, ?, ?)",
            (claim_2_id, source_id, json.dumps({"candidate_key": "claim_decide_02", "statement": "Claim two"}, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    grouped_response = client.get("/api/review/suggestions/grouped", params={"source_id": source_id})
    assert grouped_response.status_code == 200
    grouped = grouped_response.json()
    group = grouped["node_groups"][0]
    assert group["node_candidate"]["title"] == "Token Overhead"
    assert group["node_candidate"]["body"] == "Token overhead is the extra prompt/context cost added by agent tools."
    assert group["node_candidate"]["tags"] == ["agent", "token-overhead"]
    assert len(group["claims"]) == 2

    draft_response = client.post(
        "/api/mapping/draft",
        json={
            "node_candidate_id": node_candidate_id,
            "title": "Edited Token Overhead",
            "body": "Edited markdown body",
            "tags": ["edited", "token-overhead"],
            "aliases": ["TO"],
            "node_type": "concept",
            "source_id": source_id,
            "status": "pending",
        },
    )
    assert draft_response.status_code == 200
    conn = connect(paths.db)
    try:
        saved_row = conn.execute("SELECT payload_json FROM review_candidates WHERE id = ?", (node_candidate_id,)).fetchone()
        saved_payload = json.loads(saved_row["payload_json"])
    finally:
        conn.close()
    assert saved_payload["candidate_key"] == "node_decide_01"
    assert saved_payload["evidence_claim_keys"] == ["claim_decide_01", "claim_decide_02"]
    assert saved_payload["draft"]["title"] == "Edited Token Overhead"
    assert saved_payload["draft"]["tags"] == ["edited", "token-overhead"]

    grouped_after_draft = client.get("/api/review/suggestions/grouped", params={"source_id": source_id}).json()
    assert grouped_after_draft["node_groups"][0]["node_candidate"]["title"] == "Edited Token Overhead"
    assert grouped_after_draft["node_groups"][0]["node_candidate"]["body"] == "Edited markdown body"

    response = client.post(
        "/api/review/suggestions/decide-node",
        json={
            "node_candidate_id": node_candidate_id,
            "claim_candidate_ids": [claim_1_id],
            "action": "merge_into_existing",
            "target_concept_id": "token-overhead",
            "note": "claim_2 excluded as overgeneralized",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["action"] == "merge_into_existing"
    assert payload["included_claim_count"] == 1
    assert payload["excluded_claim_count"] == 1

    conn = connect(paths.db)
    try:
        decision = conn.execute("SELECT * FROM human_decisions WHERE candidate_id = ? ORDER BY decided_at DESC", (node_candidate_id,)).fetchone()
        metadata = json.loads(decision["metadata_json"])
    finally:
        conn.close()

    assert decision["decision_type"] == "merge_into_existing"
    assert metadata["surface"] == "node_centric_review"
    assert metadata["included_claim_candidate_ids"] == [claim_1_id]
    assert metadata["excluded_claim_candidate_ids"] == [claim_2_id]
    assert metadata["target_concept_id"] == "token-overhead"
