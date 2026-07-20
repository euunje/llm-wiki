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
