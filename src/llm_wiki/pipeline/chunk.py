from __future__ import annotations

import json

from llm_wiki.common import new_id, relative_to, utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_job, record_artifact, update_job
from llm_wiki.pipeline.errors import UserInputError
from llm_wiki.pipeline.locator import build_locator
from llm_wiki.pipeline.section_chunking import chunk_markdown_by_section
from llm_wiki.workspace import WorkspacePaths


def _token_count(text: str) -> int:
    return len(text.split())


def _choose_boundary(text: str, start: int, max_chars: int) -> int:
    limit = min(len(text), start + max_chars)
    if limit >= len(text):
        return len(text)
    for marker in ("\n\n", "\n", " "):
        idx = text.rfind(marker, start, limit)
        if idx > start:
            return idx + len(marker)
    return limit


def _chunk_text(source_id: str, text: str, max_chars: int, overlap_chars: int) -> list[dict[str, object]]:
    section_chunks = chunk_markdown_by_section(text, max_chars=max_chars)
    if section_chunks:
        return [
            {
                "id": new_id("chunk"),
                "source_id": source_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "token_count": _token_count(chunk.text),
                "locator": chunk.locator(source_id),
            }
            for chunk in section_chunks
        ]
    chunks: list[dict[str, object]] = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = _choose_boundary(text, start, max_chars)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "id": new_id("chunk"),
                    "source_id": source_id,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "token_count": _token_count(chunk_text),
                    "locator": build_locator(source_id, text, start, end),
                }
            )
            chunk_index += 1
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def chunk_source(workspace: WorkspacePaths, source_id: str) -> dict[str, object]:
    settings = load_settings(workspace.settings_file)
    max_chars = int(settings.get("chunking", {}).get("max_chars", 1000))
    overlap_chars = int(settings.get("chunking", {}).get("overlap_chars", 200))
    job_id = create_job(workspace.db, "chunk", target_type="source", target_id=source_id)
    update_job(workspace.db, job_id, status="running")
    conn = connect(workspace.db)
    try:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise UserInputError(f"Unknown source_id: {source_id}")
        if not row["normalized_path"]:
            raise UserInputError(f"Source {source_id} is not normalized yet")
        normalized_path = workspace.root / row["normalized_path"]
        if not normalized_path.exists():
            raise FileNotFoundError(f"Normalized file not found: {normalized_path}")
        text = normalized_path.read_text(encoding="utf-8")
        chunks = _chunk_text(source_id, text, max_chars=max_chars, overlap_chars=overlap_chars)
        now = utc_now()
        existing_rows = conn.execute(
            "SELECT id, chunk_index, text, token_count, locator_json FROM source_chunks WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        existing_by_index = {int(row["chunk_index"]): row for row in existing_rows}
        new_indexes = {int(chunk["chunk_index"]) for chunk in chunks}
        for chunk in chunks:
            chunk_index = int(chunk["chunk_index"])
            existing = existing_by_index.get(chunk_index)
            chunk_id = str(existing["id"]) if existing is not None else str(chunk["id"])
            chunk["id"] = chunk_id
            locator_json = json.dumps(chunk["locator"], ensure_ascii=False, sort_keys=True)
            if (
                existing is not None
                and str(existing["text"]) == str(chunk["text"])
                and int(existing["token_count"]) == int(chunk["token_count"])
                and str(existing["locator_json"]) == locator_json
            ):
                continue
            conn.execute(
                """
                INSERT INTO source_chunks (
                    id, source_id, chunk_index, text, token_count, locator_json,
                    embedding_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                ON CONFLICT(source_id, chunk_index) DO UPDATE SET
                    text = excluded.text,
                    token_count = excluded.token_count,
                    locator_json = excluded.locator_json,
                    embedding_status = 'pending',
                    updated_at = excluded.updated_at
                """,
                (
                    chunk_id,
                    chunk["source_id"],
                    chunk_index,
                    chunk["text"],
                    chunk["token_count"],
                    locator_json,
                    now,
                    now,
                ),
            )
        stale_ids = [row["id"] for row in existing_rows if int(row["chunk_index"]) not in new_indexes]
        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            conn.execute(f"DELETE FROM embeddings WHERE target_type = 'chunk' AND target_id IN ({placeholders})", stale_ids)
            conn.execute(f"DELETE FROM source_chunks WHERE id IN ({placeholders})", stale_ids)
        conn.execute("UPDATE sources SET pipeline_stage = 'chunked', updated_at = ? WHERE id = ?", (now, source_id))
        conn.commit()
        artifact = record_artifact(
            workspace,
            artifact_type="chunk_report",
            task_type="chunk",
            payload={
                "status": "ok",
                "source_id": source_id,
                "chunk_count": len(chunks),
                "chunk_ids": [chunk["id"] for chunk in chunks],
                "chunking": {"max_chars": max_chars, "overlap_chars": overlap_chars},
            },
            target_type="source",
            target_id=source_id,
        )
        update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
        return {
            "status": "ok",
            "source_id": source_id,
            "job_id": job_id,
            "chunk_count": len(chunks),
            "chunk_ids": [chunk["id"] for chunk in chunks],
            "chunking": {"max_chars": max_chars, "overlap_chars": overlap_chars},
            **artifact,
            "message": f"Chunked source {source_id} into {len(chunks)} chunks",
        }
    except Exception as exc:
        update_job(
            workspace.db,
            job_id,
            status="failed",
            error={"reason": str(exc), "type": exc.__class__.__name__},
        )
        raise
    finally:
        conn.close()
