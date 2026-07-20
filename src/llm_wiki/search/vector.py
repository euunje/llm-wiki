"""Phase 2 deterministic vector/RAG search over stored SQLite embeddings."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from typing import Any

from llm_wiki.common import sha256_text
from llm_wiki.pipeline.embed import _fallback_vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot / (left_norm * right_norm)


def _parse_vector(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    vector: list[float] = []
    for value in data:
        if not isinstance(value, (int, float)):
            return None
        vector.append(float(value))
    return vector or None


def _lexical_query_vector(query: str, dimension: int) -> list[float]:
    tokens = re.findall(r"[\w가-힣]+", query.lower())
    if dimension <= 0:
        return []
    if not tokens:
        return [0.0] * dimension
    vector = [0.0] * dimension
    for token in tokens:
        digest = sha256_text(token)
        for offset in range(0, min(len(digest), dimension * 2), 2):
            slot = (offset // 2) % dimension
            bucket = int(digest[offset:offset + 2], 16)
            vector[slot] += (bucket / 255.0) * 2 - 1
    return [round(value / max(len(tokens), 1), 6) for value in vector]


def _query_vector(query: str, dimension: int, backend: str, model: str) -> tuple[list[float], str]:
    if backend == "fallback_hash" or model.startswith("fallback"):
        return _fallback_vector(query, dimension=dimension), "vector_hash_fallback"
    return _lexical_query_vector(query, dimension=dimension), "vector_lexical_fallback"


def search_chunk_vectors(conn: sqlite3.Connection, query: str, limit: int = 5) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT e.target_id, e.model, e.backend, e.dimension, e.vector_json, c.source_id, c.text
        FROM embeddings e
        JOIN source_chunks c ON c.id = e.target_id
        WHERE e.target_type = 'chunk' AND e.vector_json IS NOT NULL AND e.vector_json != ''
        ORDER BY e.created_at DESC
        """
    ).fetchall()
    if not rows:
        return {
            "results": [],
            "metadata": {"attempted": False, "reason": "no_chunk_embeddings"},
        }

    groups: dict[tuple[str, str, int], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((row["model"], row["backend"], int(row["dimension"])), []).append(row)
    model, backend, dimension = max(groups.items(), key=lambda item: len(item[1]))[0]
    selected_rows = groups[(model, backend, dimension)]
    query_vector, match_type = _query_vector(query, dimension, backend, model)
    scored: list[dict[str, Any]] = []
    for row in selected_rows:
        vector = _parse_vector(row["vector_json"])
        if vector is None or len(vector) != dimension:
            continue
        score = cosine_similarity(query_vector, vector)
        scored.append(
            {
                "target_type": "chunk",
                "target_id": row["target_id"],
                "source_id": row["source_id"],
                "snippet": row["text"][:240],
                "match_type": match_type,
                "score": round(score, 6),
                "vector_model": model,
                "vector_backend": backend,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "results": scored[:limit],
        "metadata": {
            "attempted": True,
            "match_type": match_type,
            "dimension": dimension,
            "model": model,
            "backend": backend,
            "candidate_count": len(scored),
            "result_count": min(limit, len(scored)),
        },
    }
