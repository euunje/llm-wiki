from __future__ import annotations

import json
from pathlib import Path

from llm_wiki.common import ensure_parent, relative_to, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_job, record_artifact, update_job
from llm_wiki.pipeline.errors import UserInputError
from llm_wiki.workspace import WorkspacePaths


def normalize_markdown_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines).strip() + "\n"
    return normalized


def normalize_source(workspace: WorkspacePaths, source_id: str) -> dict[str, object]:
    job_id = create_job(workspace.db, "normalize", target_type="source", target_id=source_id)
    update_job(workspace.db, job_id, status="running")
    conn = connect(workspace.db)
    normalized_path: Path | None = None
    try:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise UserInputError(f"Unknown source_id: {source_id}")
        raw_path = workspace.root / row["raw_path"]
        if not raw_path.exists():
            raise FileNotFoundError(f"Raw source file not found: {raw_path}")
        normalized_text = normalize_markdown_text(raw_path.read_text(encoding="utf-8"))
        normalized_path = workspace.normalized / f"{source_id}.md"
        ensure_parent(normalized_path)
        normalized_path.write_text(normalized_text, encoding="utf-8")
        locator_policy = {
            "strategy": "character_offsets_with_heading_path",
            "normalized_newlines": True,
            "retains_markdown": True,
        }
        conn.execute(
            "UPDATE sources SET normalized_path = ?, pipeline_stage = 'normalized', updated_at = ? WHERE id = ?",
            (relative_to(workspace.root, normalized_path), utc_now(), source_id),
        )
        conn.commit()
        artifact = record_artifact(
            workspace,
            artifact_type="normalize_report",
            task_type="normalize",
            payload={
                "status": "ok",
                "source_id": source_id,
                "normalized_path": relative_to(workspace.root, normalized_path),
                "locator_policy": locator_policy,
            },
            target_type="source",
            target_id=source_id,
        )
        update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
        return {
            "status": "ok",
            "source_id": source_id,
            "job_id": job_id,
            "normalized_path": relative_to(workspace.root, normalized_path),
            "locator_policy": locator_policy,
            **artifact,
            "message": f"Normalized source {source_id}",
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
