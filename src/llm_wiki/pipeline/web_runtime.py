from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from llm_wiki.cli.phase1_placeholders import run_extract_claims, run_map
from llm_wiki.common import utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.pipeline.chunk import chunk_source
from llm_wiki.pipeline.embed import embed_target
from llm_wiki.pipeline.normalize import normalize_source
from llm_wiki.workspace import WorkspacePaths


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
        request_artifact = record_artifact(
            workspace,
            artifact_type="inbox_process_request",
            task_type="inbox_process",
            payload={
                "status": "processing",
                "source_id": source_id,
                "source_title": source["title"],
                "mode": "web_sync_pipeline",
                "retry_path": f"/api/inbox/items/{source_id}/retry",
            },
            target_type="source",
            target_id=source_id,
            run_id=run_id,
        )
        use_llm = _llm_extract_enabled(workspace)
        steps = []
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
        extract_exit, extract_payload = run_extract_claims(
            SimpleNamespace(path=str(workspace.root), source_id=source_id, use_llm=use_llm)
        )
        steps.append({"step": "extract_claims", "exit_code": extract_exit, **extract_payload})
        if extract_exit != 0:
            raise RuntimeError(extract_payload.get("message") or f"extract_claims failed for {source_id}")
        map_exit, map_payload = run_map(SimpleNamespace(path=str(workspace.root), source_id=source_id))
        steps.append({"step": "map", "exit_code": map_exit, **map_payload})
        if map_exit != 0:
            raise RuntimeError(map_payload.get("message") or f"map failed for {source_id}")
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
            "extract_mode": "llm" if use_llm else "deterministic_fallback",
            "final_state": final_state,
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
        payload = {
            "status": "failed",
            "item_id": source_id,
            "source_id": source_id,
            "job_id": orchestrator_job_id,
            "run_id": run_id,
            "mode": "web_sync_pipeline",
            "error": {"reason": str(exc), "type": exc.__class__.__name__},
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
