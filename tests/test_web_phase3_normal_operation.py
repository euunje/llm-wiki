from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.db.schema import connect
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.delenv("LLM_WIKI_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LOCAL_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LLM_WIKI_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_WIKI_CHAT_MODEL", raising=False)
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def _process_text_source(client) -> str:
    ingest = client.post(
        "/api/inbox/text",
        json={
            "title": "Graph Retrieval Notes",
            "text": "Graph retrieval improves grounding for answer generation and supports evidence-based mapping.",
        },
    )
    assert ingest.status_code == 200
    source_id = ingest.json()["item"]["source_id"]
    process = client.post("/api/inbox/process", json={"item_ids": [source_id]})
    assert process.status_code == 200
    item = process.json()["items"][0]
    assert item["final_state"] == "needs_mapping"
    assert item["page_count"] >= 1
    assert item["wiki_pages"]
    assert item["quality_gate"]["status"] in {"ok", "repaired"}
    assert item["quality_gate"]["source_common_tags"]
    assert item["llm_page_candidate_attempt"]["attempted"] is False
    return source_id


def test_inbox_process_llm_mode_reads_active_page_candidate_prompt(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from llm_wiki.schema.prompts import create_prompt_version

    client, paths = _client(workspace, monkeypatch)
    marker = "WEB_ACTIVE_PAGE_CANDIDATE_PROMPT_MARKER"
    prompt_id = create_prompt_version(
        paths.db,
        "wiki_page_candidates_initial",
        "web-active-page-candidate-test",
        f"{marker}\nReturn ONLY JSON with document_type, target_candidate_count, and candidates for page candidate generation.",
        state="confirmed",
        bypass_test=True,
    )
    conn = connect(paths.db)
    try:
        conn.execute("UPDATE prompt_versions SET confirmed_at = '9999-01-01T00:00:00Z' WHERE id = ?", (prompt_id,))
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("LLM_WIKI_API_KEY", "web-llm-test-key")
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

    seen_system_prompts: list[str] = []

    def fake_call_json_task(workspace_arg, *, model_id: str, system_prompt: str, user_prompt: str):
        seen_system_prompts.append(system_prompt)
        return {
            "parsed_json": {
                "document_type": "analysis",
                "target_candidate_count": 1,
                "candidates": [
                    {
                        "title": "LLM Web Prompt Wiring",
                        "summary": "Active prompt version is used by Web Inbox LLM page candidate generation.",
                        "node_type": "concept",
                        "tags": ["concept", "web", "prompt"],
                        "draft_body": "# LLM Web Prompt Wiring\n\nWeb Inbox uses the active page candidate prompt.",
                    }
                ],
            },
            "content": "{}",
            "json_repair_applied": False,
            "http_response_size_bytes": 2,
            "api_key_present": True,
        }

    monkeypatch.setattr("llm_wiki.pipeline.wiki_ingest_llm.call_json_task", fake_call_json_task)
    monkeypatch.setattr("llm_wiki.pipeline.web_runtime.run_extract_claims", lambda args: (0, {"status": "ok", "candidate_count": 0, "mode": "fake"}))
    monkeypatch.setattr("llm_wiki.pipeline.web_runtime.run_map", lambda args: (0, {"status": "ok", "candidate_count": 0, "mode": "fake"}))
    ingest = client.post(
        "/api/inbox/text",
        json={
            "title": "LLM Web Prompt Source",
            "text": "Web Inbox should route page candidate generation through active prompt_versions.",
        },
    )
    assert ingest.status_code == 200
    source_id = ingest.json()["item"]["source_id"]
    process = client.post("/api/inbox/process", json={"item_ids": [source_id]})
    assert process.status_code == 200
    item = process.json()["items"][0]
    assert item["status"] == "ok"
    assert item["llm_page_candidate_attempt"]["attempted"] is True
    assert item["llm_page_candidate_attempt"]["status"] == "parsed"
    assert item["cli_equivalent"]["use_llm"] is True
    assert seen_system_prompts and marker in seen_system_prompts[0]


def test_inbox_process_creates_real_job_run_and_artifacts(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    source_id = _process_text_source(client)

    status_payload = client.get("/api/inbox/status")
    assert status_payload.status_code == 200
    assert status_payload.json()["needs_mapping_count"] >= 1

    conn = connect(paths.db)
    try:
        source = conn.execute(
            "SELECT pipeline_stage, review_status FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        inbox_job = conn.execute(
            "SELECT status FROM jobs WHERE target_id = ? AND job_type = 'inbox_process' ORDER BY created_at DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        inbox_run = conn.execute(
            "SELECT status FROM agent_runs WHERE job_id IN (SELECT id FROM jobs WHERE target_id = ? AND job_type = 'inbox_process') ORDER BY started_at DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        artifact_rows = conn.execute(
            "SELECT artifact_type FROM artifacts WHERE target_id = ? ORDER BY created_at",
            (source_id,),
        ).fetchall()
        pending_candidates = conn.execute(
            "SELECT COUNT(*) FROM review_candidates WHERE source_id = ? AND status = 'pending'",
            (source_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    artifact_types = {row[0] for row in artifact_rows}
    assert source["pipeline_stage"] == "candidate_generated"
    assert source["review_status"] == "needs_mapping"
    assert inbox_job["status"] == "succeeded"
    assert inbox_run["status"] == "succeeded"
    assert {"inbox_process_request", "inbox_process_result", "candidate_contract"}.issubset(artifact_types)
    assert pending_candidates >= 1

    page_review = client.get(f"/api/review/wiki-pages?source_id={source_id}")
    assert page_review.status_code == 200
    page_payload = page_review.json()
    assert page_payload["status"] == "ok"
    assert page_payload["count"] >= 1
    assert all(page["review_object"] == "wiki_page" for page in page_payload["pages"])
    assert any("Graph Retrieval" in page["title"] or "Graph Retrieval" in page["body_preview"] for page in page_payload["pages"])


def test_mapping_preview_then_confirm_create_new_writes_wiki_page(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    _process_text_source(client)

    mapping_candidates = client.get("/api/mapping/candidates")
    assert mapping_candidates.status_code == 200
    mapping_candidate = next(item for item in mapping_candidates.json()["candidates"] if item["candidate_type"] == "mapping")

    preview = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "create_new",
            "metadata": {"step": "page_mapping"},
        },
    )
    assert preview.status_code == 200
    assert preview.json()["status"] == "preview_ready"
    concept_id = preview.json()["effect"]["target_concept_id"]
    preview_decision_id = preview.json()["decision_id"]

    confirm = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "create_new",
            "metadata": {"step": "relationship_validate", "preview_decision_id": preview_decision_id},
        },
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "applied"
    assert confirm.json()["effect"]["wiki_path"] == f"vault/10_Wiki/concepts/{concept_id}.md"

    wiki_page = paths.wiki_concepts / f"{concept_id}.md"
    assert wiki_page.exists()
    page_text = wiki_page.read_text(encoding="utf-8")
    assert "Graph Retrieval Notes" in page_text
    assert "evidence-based mapping" in page_text

    detail = client.get(f"/api/mapping/candidates/{mapping_candidate['id']}")
    assert detail.status_code == 200
    assert detail.json()["candidate"]["latest_effect"]["index_status"] in {"pending", "already_generated"}

    wiki_lookup = client.get(f"/api/wiki/pages/{concept_id}")
    assert wiki_lookup.status_code == 200
    assert wiki_lookup.json()["page"]["title"] == "Graph Retrieval Notes"

    conn = connect(paths.db)
    try:
        candidate_status = conn.execute(
            "SELECT status FROM review_candidates WHERE id = ?",
            (mapping_candidate["id"],),
        ).fetchone()[0]
        decisions = [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT metadata_json FROM human_decisions WHERE candidate_id = ? ORDER BY decided_at",
                (mapping_candidate["id"],),
            ).fetchall()
        ]
    finally:
        conn.close()

    assert candidate_status == "approved"
    assert decisions[0]["decision_phase"] == "preview"
    assert decisions[-1]["decision_phase"] == "confirm"
    assert decisions[-1]["effect"]["wiki_path"] == f"vault/10_Wiki/concepts/{concept_id}.md"


def test_mapping_add_vs_merge_use_distinct_policies(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-3-NO-04: Add appends (no dedup); Merge dedups into existing aliases/claims.

    Add/Merge must produce distinct wiki body behavior, and Confirm must reference
    the recorded preview_decision_id (422 otherwise).
    """
    from llm_wiki.db.schema import connect
    client, paths = _client(workspace, monkeypatch)
    _process_text_source(client)

    candidates = client.get("/api/mapping/candidates").json()["candidates"]
    mapping_candidate = next(c for c in candidates if c["candidate_type"] == "mapping")

    # Seed a target wiki page manually so Add and Merge have something to write into.
    target_concept_id = "shared-concept"
    target_path = paths.wiki_concepts / f"{target_concept_id}.md"
    target_path.write_text(
        "# Shared Concept\n\nInitial summary.\n\n## Aliases\n\n- existing-alias\n\n## Claims\n\n- existing claim\n",
        encoding="utf-8",
    )

    # Preview ADD.
    preview_add = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "add",
            "metadata": {"step": "page_mapping", "target_concept_id": target_concept_id},
        },
    )
    assert preview_add.status_code == 200
    add_preview_id = preview_add.json()["decision_id"]

    # Confirm ADD.
    confirm_add = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "add",
            "metadata": {
                "step": "relationship_validate",
                "preview_decision_id": add_preview_id,
                "target_concept_id": target_concept_id,
            },
        },
    )
    assert confirm_add.status_code == 200, confirm_add.text
    assert confirm_add.json()["effect"]["merge_policy"] == "append"
    add_text = target_path.read_text(encoding="utf-8")

    # Preview MERGE.
    preview_merge = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "merge",
            "metadata": {"step": "page_mapping", "target_concept_id": target_concept_id},
        },
    )
    assert preview_merge.status_code == 200
    merge_preview_id = preview_merge.json()["decision_id"]

    # Confirm MERGE.
    confirm_merge = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "merge",
            "metadata": {
                "step": "relationship_validate",
                "preview_decision_id": merge_preview_id,
                "target_concept_id": target_concept_id,
            },
        },
    )
    assert confirm_merge.status_code == 200
    assert confirm_merge.json()["effect"]["merge_policy"] == "dedup_merge"
    merge_text = target_path.read_text(encoding="utf-8")

    # The two policies produce different final texts: ADD keeps the original
    # alias plus the appended one (no dedup), MERGE keeps the dedup'd set.
    assert add_text != merge_text, "Add and Merge must produce distinct wiki content"
    assert "existing-alias" in add_text
    assert "existing-alias" in merge_text

    # Confirm without preview_decision_id must return 422.
    no_id = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": mapping_candidate["id"],
            "action": "add",
            "metadata": {"step": "relationship_validate"},
        },
    )
    assert no_id.status_code == 422
