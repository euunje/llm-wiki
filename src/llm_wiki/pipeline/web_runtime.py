from __future__ import annotations

from typing import Any

from llm_wiki.common import utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.pipeline.chunk import chunk_source
from llm_wiki.pipeline.embed import embed_target
from llm_wiki.pipeline.normalize import normalize_source
from llm_wiki.pipeline.wiki_ingest import run_wiki_ingest_pipeline
from llm_wiki.workspace import WorkspacePaths


def _cli_equivalent(source_id: str, *, use_llm: bool) -> dict[str, Any]:
    return {
        "mode": "shared_pipeline",
        "command": f"wiki web-pipeline inbox-process --source-id {source_id}{' --llm' if use_llm else ' --deterministic'}",
        "python_call": "process_inbox_source(workspace, source_id)",
        "source_id": source_id,
        "use_llm": use_llm,
    }


def _markdown_mentions_source_id(path, source_id: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return f"source_ids:\n- {source_id}" in text or f"source_ids: [{source_id}]" in text or f"id: {source_id}" in text


def reset_inbox_source_for_full_retry(workspace: WorkspacePaths, source_id: str) -> dict[str, Any]:
    """Remove generated artifacts for a source before a Web full retry.

    Raw source registration and historical jobs/artifacts are preserved. Generated
    wiki pages, source summary, review candidates, chunks, embeddings, and the
    normalized copy are removed so the next process call starts from the raw
    source and cannot leave duplicate/stale generated items behind.
    """
    deleted_files: list[str] = []
    for folder in (workspace.wiki_concepts, workspace.wiki_sources):
        if not folder.exists():
            continue
        for path in folder.glob("*.md"):
            if _markdown_mentions_source_id(path, source_id):
                path.unlink(missing_ok=True)
                deleted_files.append(str(path.relative_to(workspace.root)))

    conn = connect(workspace.db)
    try:
        source = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not source:
            raise ValueError(f"Unknown source_id: {source_id}")
        normalized_path = str(source["normalized_path"] or "")
        if normalized_path:
            normalized_file = (workspace.root / normalized_path).resolve()
            try:
                normalized_file.relative_to(workspace.root.resolve())
                normalized_file.unlink(missing_ok=True)
                deleted_files.append(normalized_path)
            except Exception:
                pass
        candidate_ids = [str(row["id"]) for row in conn.execute("SELECT id FROM review_candidates WHERE source_id = ?", (source_id,)).fetchall()]
        if candidate_ids:
            placeholders = ", ".join("?" for _ in candidate_ids)
            conn.execute(f"DELETE FROM human_decisions WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            conn.execute(f"DELETE FROM retry_instructions WHERE target_candidate_id IN ({placeholders})", tuple(candidate_ids))
        conn.execute("DELETE FROM review_candidates WHERE source_id = ?", (source_id,))
        conn.execute(
            "DELETE FROM embeddings WHERE target_type = 'chunk' AND target_id IN (SELECT id FROM source_chunks WHERE source_id = ?)",
            (source_id,),
        )
        conn.execute("DROP TRIGGER IF EXISTS source_chunks_ad")
        conn.execute("DELETE FROM source_chunks_fts WHERE source_id = ?", (source_id,))
        conn.execute("DELETE FROM source_chunks WHERE source_id = ?", (source_id,))
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS source_chunks_ad AFTER DELETE ON source_chunks BEGIN
              INSERT INTO source_chunks_fts(source_chunks_fts, rowid, chunk_id, source_id, text)
              VALUES('delete', old.rowid, old.id, old.source_id, old.text);
            END
            """
        )
        conn.execute(
            "UPDATE sources SET normalized_path = NULL, pipeline_stage = 'created', review_status = 'pending', updated_at = ? WHERE id = ?",
            (utc_now(), source_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"mode": "full_regeneration", "source_id": source_id, "deleted_files": deleted_files}


class PipelineStepError(RuntimeError):
    def __init__(self, stage: str, payload: dict[str, Any]):
        self.stage = stage
        self.payload = payload
        llm_attempt = payload.get("llm_attempt") if isinstance(payload, dict) else None
        if isinstance(llm_attempt, dict) and llm_attempt.get("reason"):
            reason = str(llm_attempt.get("reason"))
            error_type = str(llm_attempt.get("type") or "PipelineStepError")
        else:
            reason = str(payload.get("message") or f"{stage} failed")
            error_type = str(payload.get("type") or "PipelineStepError")
        self.error = {"stage": stage, "reason": reason, "type": error_type}
        super().__init__(reason)


def _llm_extract_enabled(workspace: WorkspacePaths) -> bool:
    llm_settings = load_settings(workspace.settings_file).get("llm") or {}
    endpoint = bool(str(llm_settings.get("endpoint") or "").strip())
    api_key_env = str(llm_settings.get("api_key_env") or "LLM_WIKI_API_KEY")
    chat_model = bool(
        str(llm_settings.get("default_chat_model") or "").strip()
        or str(((llm_settings.get("models") or {}).get("chat_default") or {}).get("model_name") or "").strip()
    )
    import os

    return endpoint and chat_model and bool(os.environ.get(api_key_env))


def process_inbox_source(workspace: WorkspacePaths, source_id: str, *, job_id: str | None = None) -> dict[str, Any]:
    orchestrator_job_id = job_id or create_job(
        workspace.db,
        "inbox_process",
        target_type="source",
        target_id=source_id,
        input_refs=[{"kind": "source", "id": source_id}],
    )
    update_job(workspace.db, orchestrator_job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=orchestrator_job_id,
        agent_type="web_pipeline_orchestrator",
        task_type="inbox_process",
        provider="web",
        input_refs=[{"kind": "source", "id": source_id}],
    )
    try:
        conn = connect(workspace.db)
        try:
            source = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            if not source:
                raise ValueError(f"Unknown source_id: {source_id}")
            existing_chunk_count = int(
                conn.execute("SELECT COUNT(*) FROM source_chunks WHERE source_id = ?", (source_id,)).fetchone()[0]
            )
            existing_embedding_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE target_type = 'chunk' AND target_id IN (SELECT id FROM source_chunks WHERE source_id = ?)",
                    (source_id,),
                ).fetchone()[0]
            )
            normalized_ready = bool(source["normalized_path"])
            conn.execute(
                "UPDATE sources SET pipeline_stage = 'processing', updated_at = ? WHERE id = ?",
                (utc_now(), source_id),
            )
            conn.commit()
        finally:
            conn.close()
        use_llm = _llm_extract_enabled(workspace)
        request_artifact = record_artifact(
            workspace,
            artifact_type="inbox_process_request",
            task_type="inbox_process",
            payload={
                "status": "processing",
                "source_id": source_id,
                "source_title": source["title"],
                "mode": "web_sync_pipeline",
                "cli_equivalent": _cli_equivalent(source_id, use_llm=use_llm),
                "retry_path": f"/api/inbox/items/{source_id}/retry",
            },
            target_type="source",
            target_id=source_id,
            run_id=run_id,
        )
        steps = []
        wiki_payload = run_wiki_ingest_pipeline(
            workspace,
            source_id=source_id,
            use_llm=use_llm,
            persist_review_candidates=True,
            review_run_id=run_id,
        )
        steps.append({"step": "wiki_ingest", **wiki_payload})
        conn = connect(workspace.db)
        try:
            source = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            existing_chunk_count = int(
                conn.execute("SELECT COUNT(*) FROM source_chunks WHERE source_id = ?", (source_id,)).fetchone()[0]
            )
            existing_embedding_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE target_type = 'chunk' AND target_id IN (SELECT id FROM source_chunks WHERE source_id = ?)",
                    (source_id,),
                ).fetchone()[0]
            )
            normalized_ready = bool(source["normalized_path"])
        finally:
            conn.close()
        if normalized_ready:
            steps.append({"step": "normalize", "status": "ok", "mode": "reused_existing"})
        else:
            steps.append({"step": "normalize", **normalize_source(workspace, source_id)})
        if existing_chunk_count > 0:
            steps.append({"step": "chunk", "status": "ok", "mode": "reused_existing", "chunk_count": existing_chunk_count})
        else:
            steps.append({"step": "chunk", **chunk_source(workspace, source_id)})
        if existing_embedding_count > 0:
            steps.append({"step": "embed", "status": "ok", "mode": "reused_existing", "embedding_count": existing_embedding_count})
        else:
            steps.append({"step": "embed", **embed_target(workspace, f"source:{source_id}")})
        steps.append(
            {
                "step": "publish_mapping_candidates",
                "status": "ok",
                "mode": "wiki_pages_to_review_candidates",
                "candidate_count": len(wiki_payload.get("persisted_review_candidates") or []),
            }
        )
        conn = connect(workspace.db)
        try:
            pending_candidates = int(
                conn.execute("SELECT COUNT(*) FROM review_candidates WHERE source_id = ? AND status = 'pending'", (source_id,)).fetchone()[0]
            )
            total_candidates = int(conn.execute("SELECT COUNT(*) FROM review_candidates WHERE source_id = ?", (source_id,)).fetchone()[0])
            final_state = "needs_mapping" if pending_candidates else "completed"
            conn.execute(
                "UPDATE sources SET pipeline_stage = ?, review_status = ?, updated_at = ? WHERE id = ?",
                (
                    "candidate_generated" if pending_candidates else "embedded",
                    final_state,
                    utc_now(),
                    source_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        payload = {
            "status": "ok",
            "item_id": source_id,
            "source_id": source_id,
            "job_id": orchestrator_job_id,
            "run_id": run_id,
            "mode": "web_sync_pipeline",
            "cli_equivalent": _cli_equivalent(source_id, use_llm=use_llm),
            "extract_mode": "llm" if use_llm else "deterministic_fallback",
            "final_state": final_state,
            "page_count": wiki_payload.get("page_count", 0),
            "wiki_pages": wiki_payload.get("wiki_pages", []),
            "persisted_review_candidates": wiki_payload.get("persisted_review_candidates", []),
            "source_summary_path": wiki_payload.get("source_summary_path"),
            "quality_gate": wiki_payload.get("quality_gate"),
            "llm_page_candidate_attempt": wiki_payload.get("llm_page_candidate_attempt"),
            "wiki_artifact_id": wiki_payload.get("artifact_id"),
            "candidate_count": total_candidates,
            "pending_candidate_count": pending_candidates,
            "retry_path": f"/api/inbox/items/{source_id}/retry",
            "steps": steps,
            "request_artifact": request_artifact,
        }
        artifact = record_artifact(
            workspace,
            artifact_type="inbox_process_result",
            task_type="inbox_process",
            payload=payload,
            target_type="source",
            target_id=source_id,
            run_id=run_id,
        )
        update_agent_run(
            workspace.db,
            run_id,
            status="succeeded",
            output_refs=[request_artifact, artifact],
            artifact_id=artifact["artifact_id"],
        )
        update_job(workspace.db, orchestrator_job_id, status="succeeded", output_refs=[request_artifact, artifact])
        return {**payload, **artifact}
    except Exception as exc:
        conn = connect(workspace.db)
        try:
            conn.execute(
                "UPDATE sources SET pipeline_stage = 'failed', review_status = 'failed', updated_at = ? WHERE id = ?",
                (utc_now(), source_id),
            )
            conn.commit()
        finally:
            conn.close()
        error_payload = getattr(exc, "error", None)
        if not isinstance(error_payload, dict):
            error_payload = {"reason": str(exc), "type": exc.__class__.__name__}
        error_payload.setdefault("stage", getattr(exc, "stage", "inbox_process"))
        payload = {
            "status": "failed",
            "item_id": source_id,
            "source_id": source_id,
            "job_id": orchestrator_job_id,
            "run_id": run_id,
            "mode": "web_sync_pipeline",
            "cli_equivalent": _cli_equivalent(source_id, use_llm=_llm_extract_enabled(workspace)),
            "error": error_payload,
            "retry_path": f"/api/inbox/items/{source_id}/retry",
        }
        artifact = record_artifact(
            workspace,
            artifact_type="inbox_process_error",
            task_type="inbox_process",
            payload=payload,
            target_type="source",
            target_id=source_id,
            run_id=run_id,
        )
        update_agent_run(
            workspace.db,
            run_id,
            status="failed",
            output_refs=[artifact],
            artifact_id=artifact["artifact_id"],
            error=payload["error"],
        )
        update_job(workspace.db, orchestrator_job_id, status="failed", output_refs=[artifact], error=payload["error"])
        return {**payload, **artifact}
