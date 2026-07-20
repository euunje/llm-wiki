"""Reusable search and ask helpers for CLI and Web APIs."""

from __future__ import annotations

import sqlite3
from typing import Any

from llm_wiki.db.schema import connect, inspect_database
from llm_wiki.workspace import WorkspacePaths, resolve_workspace

from .vector import search_chunk_vectors

SEARCH_MODES = {"combined", "fts", "vector", "metadata"}


def _fts5_safe_query(query: str) -> str:
    terms = [part for part in query.replace('"', " ").split() if part]
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)


def _coerce_workspace(workspace: WorkspacePaths | str | None) -> WorkspacePaths:
    return workspace if isinstance(workspace, WorkspacePaths) else resolve_workspace(workspace)


def _clamp_limit(limit: int | None, *, default: int = 10, minimum: int = 1, maximum: int = 100) -> int:
    try:
        value = int(limit if limit is not None else default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _metadata_rows(conn: sqlite3.Connection, query: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, title FROM sources WHERE title LIKE ? OR metadata_json LIKE ? LIMIT ?",
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()
    return [{"target_type": "source", "target_id": row[0], "title": row[1], "match_type": "metadata"} for row in rows]


def search_workspace(workspace: WorkspacePaths | str | None, query: str, limit: int = 10, mode: str = "combined") -> dict[str, Any]:
    workspace_paths = _coerce_workspace(workspace)
    normalized_query = (query or "").strip()
    normalized_mode = (mode or "combined").strip().lower()
    if normalized_mode not in SEARCH_MODES:
        raise ValueError(f"Unsupported search mode: {mode}")
    limit_value = _clamp_limit(limit)
    if not normalized_query:
        return {
            "status": "ok",
            "query": "",
            "mode": normalized_mode,
            "count": 0,
            "results": [],
            "metadata": {"fts": {"enabled": False, "result_count": 0}, "vector": {"attempted": False, "result_count": 0}, "metadata": {"result_count": 0}},
            "workspace": str(workspace_paths.root),
            "message": "No query provided",
        }

    db_info = inspect_database(workspace_paths.db)
    conn = connect(workspace_paths.db)
    try:
        fts_results: list[dict[str, Any]] = []
        if db_info.get("fts5"):
            try:
                rows = conn.execute(
                    "SELECT chunk_id, source_id, snippet(source_chunks_fts, 2, '[', ']', '…', 12) AS snippet FROM source_chunks_fts WHERE source_chunks_fts MATCH ? LIMIT ?",
                    (normalized_query, limit_value),
                ).fetchall()
            except Exception:
                rows = conn.execute(
                    "SELECT chunk_id, source_id, snippet(source_chunks_fts, 2, '[', ']', '…', 12) AS snippet FROM source_chunks_fts WHERE source_chunks_fts MATCH ? LIMIT ?",
                    (_fts5_safe_query(normalized_query), limit_value),
                ).fetchall()
            fts_results = [{"target_type": "chunk", "target_id": row[0], "source_id": row[1], "snippet": row[2], "match_type": "fts"} for row in rows]

        vector_search = search_chunk_vectors(conn, normalized_query, limit=limit_value)
        vector_results = list(vector_search.get("results") or [])
        metadata_results = _metadata_rows(conn, normalized_query, limit_value)
    finally:
        conn.close()

    seen_chunk_ids = {item["target_id"] for item in fts_results if item.get("target_type") == "chunk"}
    combined_vector_results = [item for item in vector_results if item.get("target_id") not in seen_chunk_ids]

    if normalized_mode == "fts":
        results = fts_results[:limit_value]
    elif normalized_mode == "vector":
        results = vector_results[:limit_value]
    elif normalized_mode == "metadata":
        results = metadata_results[:limit_value]
    else:
        results = [*fts_results]
        results.extend(combined_vector_results)
        if not results:
            results.extend(metadata_results)
        results = results[:limit_value]

    metadata: dict[str, Any] = {
        "fts": {"enabled": bool(db_info.get("fts5")), "result_count": len(fts_results)},
        "vector": {**(vector_search.get("metadata") or {}), "result_count": len(vector_results if normalized_mode == "vector" else (combined_vector_results if (vector_search.get("metadata") or {}).get("attempted") else []))},
        "metadata": {"result_count": len(metadata_results)},
    }
    return {
        "status": "ok",
        "query": normalized_query,
        "mode": normalized_mode,
        "count": len(results),
        "results": results,
        "metadata": metadata,
        "workspace": str(workspace_paths.root),
        "message": f"Found {len(results)} result(s)",
    }


def ask_workspace(workspace: WorkspacePaths | str | None, query: str, limit: int = 3) -> dict[str, Any]:
    workspace_paths = _coerce_workspace(workspace)
    normalized_query = (query or "").strip()
    search_payload = search_workspace(workspace_paths, normalized_query, limit=max(limit, 5), mode="combined")
    evidence_refs = [
        {
            "source_id": item.get("source_id"),
            "target_type": item.get("target_type"),
            "target_id": item.get("target_id"),
            "match_type": item.get("match_type"),
            "snippet": item.get("snippet") or item.get("title") or "",
        }
        for item in (search_payload.get("results") or [])[: _clamp_limit(limit, default=3, minimum=1, maximum=10)]
        if isinstance(item, dict)
    ]
    answer = (
        f"질문 '{normalized_query}'에 대해 현재 index에서 확인된 근거를 바탕으로 답변 후보를 생성했습니다. "
        "한국어 중심 설명을 유지하고 기술 용어와 고유명사는 원문 표기를 보존합니다."
        if normalized_query
        else "질문이 비어 있어 답변 근거를 생성하지 않았습니다."
    )
    return {
        "status": "ok",
        "query": normalized_query,
        "answer": answer,
        "answer_placeholder": answer,
        "evidence_refs": evidence_refs,
        "search_metadata": search_payload.get("metadata") or {},
        "search_results": search_payload.get("results") or [],
        "workspace": str(workspace_paths.root),
        "message": f"Prepared answer with {len(evidence_refs)} evidence ref(s)",
    }
