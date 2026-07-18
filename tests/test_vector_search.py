from __future__ import annotations

import json
from pathlib import Path

from llm_wiki.cli import build_parser
from llm_wiki.db.schema import connect
from llm_wiki.pipeline.embed import _fallback_vector
from llm_wiki.search import cosine_similarity


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _ensure_init(workspace: Path) -> None:
    _invoke(["init"], workspace)


def test_cosine_similarity_ranks_closest_vector() -> None:
    exact = cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    partial = cosine_similarity([1.0, 0.0, 0.0], [0.5, 0.5, 0.0])
    opposite = cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
    assert exact > partial > opposite


def test_search_includes_fts_and_vector_metadata(workspace: Path) -> None:
    _ensure_init(workspace)
    source_id = _invoke(["ingest-text", "Vector Search Note", "--text", "RAG pipelines improve retrieval and answer grounding."], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _, chunk_payload = _invoke(["chunk", source_id], workspace)
    chunk_id = chunk_payload["chunk_ids"][0]
    query_vector = _fallback_vector("RAG", dimension=16)

    conn = connect(workspace / "data" / "wiki.sqlite")
    try:
        conn.execute(
            """
            INSERT INTO source_chunks (
                id, source_id, chunk_index, text, token_count, locator_json,
                embedding_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'embedded', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (
                "chunk_vector_only",
                source_id,
                1,
                "Deterministic retrieval context chunk.",
                4,
                json.dumps({"kind": "manual_test"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO embeddings (
                id, target_type, target_id, model, backend, dimension, vector_blob, vector_json,
                index_status, generated_at, created_at, updated_at
            ) VALUES (?, 'chunk', ?, ?, ?, ?, NULL, ?, 'stored', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (
                "embedding_test_1",
                chunk_id,
                "fallback-hash-v1",
                "fallback_hash",
                16,
                json.dumps([0.2] * 16),
            ),
        )
        conn.execute(
            """
            INSERT INTO embeddings (
                id, target_type, target_id, model, backend, dimension, vector_blob, vector_json,
                index_status, generated_at, created_at, updated_at
            ) VALUES (?, 'chunk', ?, ?, ?, ?, NULL, ?, 'stored', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (
                "embedding_test_2",
                "chunk_vector_only",
                "fallback-hash-v1",
                "fallback_hash",
                16,
                json.dumps(query_vector),
            ),
        )
        conn.execute(
            "UPDATE source_chunks SET embedding_status = 'embedded' WHERE id = ?",
            (chunk_id,),
        )
        conn.commit()
    finally:
        conn.close()

    _, search = _invoke(["search", "RAG"], workspace)
    assert search["status"] == "ok"
    assert search["metadata"]["fts"]["enabled"] is True
    assert "vector" in search["metadata"]
    assert search["metadata"]["vector"]["attempted"] is True
    assert any(item["match_type"] == "fts" for item in search["results"])
    assert any(item["match_type"].startswith("vector_") for item in search["results"])
