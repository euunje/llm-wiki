from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import utc_now
from llm_wiki.db.schema import connect
from llm_wiki.pipeline.embed import _fallback_vector
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    parser = build_parser()
    args = parser.parse_args([*cli_args, "--path", str(path), "--json"])
    return args.handler(args)


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


def test_api_search_empty_workspace_reports_no_vector_attempt(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/api/search", params={"q": "RAG"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["results"] == []
    assert payload["metadata"]["vector"]["attempted"] is False


def test_api_search_returns_fts_or_metadata_result_after_chunking(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    client, _paths = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "short-note.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)

    response = client.get("/api/search", params={"q": "pipeline", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] >= 1
    assert any(item["match_type"] in {"fts", "metadata"} for item in payload["results"])


def test_api_search_returns_vector_result_metadata_after_seeded_embeddings(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest-text", "Vector Search", "--text", "RAG pipelines improve retrieval and grounding."], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _, chunk_payload = _invoke(["chunk", source_id], workspace)
    chunk_id = chunk_payload["chunk_ids"][0]
    query_vector = _fallback_vector("RAG", dimension=16)
    now = utc_now()

    conn = connect(paths.db)
    try:
        conn.execute(
            """
            INSERT INTO embeddings (
                id, target_type, target_id, model, backend, dimension, vector_blob, vector_json,
                index_status, generated_at, created_at, updated_at
            ) VALUES (?, 'chunk', ?, ?, ?, ?, NULL, ?, 'stored', ?, ?, ?)
            """,
            ("embedding_test_api", chunk_id, "fallback-hash-v1", "fallback_hash", 16, json.dumps(query_vector), now, now, now),
        )
        conn.execute("UPDATE source_chunks SET embedding_status = 'embedded', updated_at = ? WHERE id = ?", (now, chunk_id))
        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/search", params={"q": "RAG", "mode": "vector"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] >= 1
    vector_result = payload["results"][0]
    assert vector_result["match_type"].startswith("vector_")
    assert isinstance(vector_result["score"], float)
    assert vector_result["vector_model"] == "fallback-hash-v1"
    assert vector_result["vector_backend"] == "fallback_hash"
