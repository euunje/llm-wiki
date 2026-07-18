from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_wiki.common import ensure_parent, json_dumps, new_id, relative_to, sha256_text, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.workspace import WorkspacePaths


def _validate_artifact_id(candidate: str, field_name: str, artifact_root: Path) -> str:
    """Sanitize and validate an artifact id component for path containment.

    Rejects empty strings.  Replaces path separators (/, \\), parent traversals
    (..), NUL bytes, and other suspicious characters with underscore.  After
    sanitization, confirms the candidate would resolve inside artifact_root
    (not above it, not as an absolute path).  Raises ValueError with a clear
    message on any violation.
    """
    if not candidate:
        raise ValueError(f"{field_name} must not be empty")

    # Replace path separators, parent traversals, and NUL with underscore
    sanitized = re.sub(r"[/\\.\x00]+", "_", candidate)

    # Collapse multiple underscores
    sanitized = re.sub(r"__+", "_", sanitized)
    sanitized = sanitized.strip("_")

    if not sanitized:
        raise ValueError(f"{field_name} contains no valid characters after sanitization: {candidate!r}")

    # Verify the final resolved path is contained within artifact_root
    candidate_path = (artifact_root / sanitized).resolve()
    try:
        candidate_path.relative_to(artifact_root.resolve())
    except ValueError:
        raise ValueError(
            f"{field_name} would resolve outside the artifacts directory after sanitization: {candidate!r}"
        )

    return sanitized


def create_job(
    db_path: Path,
    job_type: str,
    target_type: str | None = None,
    target_id: str | None = None,
    input_refs: list[dict[str, Any]] | None = None,
) -> str:
    job_id = new_id("job")
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO jobs (id, job_type, target_type, target_id, status, input_refs_json, output_refs_json, created_at)
            VALUES (?, ?, ?, ?, 'queued', ?, '[]', ?)
            """,
            (job_id, job_type, target_type, target_id, json.dumps(input_refs or []), utc_now()),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def update_job(
    db_path: Path,
    job_id: str,
    *,
    status: str,
    output_refs: list[dict[str, Any]] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    conn = connect(db_path)
    try:
        now = utc_now()
        started_at = now if status == "running" else None
        finished_at = now if status in {"succeeded", "failed", "cancelled", "needs_review"} else None
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                output_refs_json = COALESCE(?, output_refs_json),
                error_json = ?,
                started_at = COALESCE(started_at, ?),
                finished_at = COALESCE(?, finished_at)
            WHERE id = ?
            """,
            (
                status,
                json.dumps(output_refs) if output_refs is not None else None,
                json.dumps(error) if error is not None else None,
                started_at,
                finished_at,
                job_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_artifact(
    workspace: WorkspacePaths,
    artifact_type: str,
    task_type: str,
    payload: dict[str, Any],
    target_type: str | None = None,
    target_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, str]:
    artifact_id = new_id("artifact")
    # Sanitize target_id and run_id to prevent path traversal.
    # run_id defaults to artifact_id (safe UUID), but if explicitly provided
    # it still gets sanitized for defence in depth.
    safe_target_id = _validate_artifact_id(
        target_id or "global", "target_id", workspace.artifacts
    )
    safe_run_id = _validate_artifact_id(
        run_id or artifact_id, "run_id", workspace.artifacts
    )
    artifact_dir = workspace.artifacts / task_type / safe_target_id
    artifact_path = artifact_dir / f"{safe_run_id}.json"
    ensure_parent(artifact_path)
    content = json_dumps(payload)
    artifact_path.write_text(content + "\n", encoding="utf-8")
    if workspace.db.exists():
        conn = connect(workspace.db)
        try:
            conn.execute(
                """
                INSERT INTO artifacts (id, artifact_type, task_type, target_type, target_id, run_id, path, content_hash, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)
                """,
                (
                    artifact_id,
                    artifact_type,
                    task_type,
                    target_type,
                    target_id,
                    run_id,
                    relative_to(workspace.root, artifact_path),
                    sha256_text(content),
                    utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "artifact_id": artifact_id,
        "artifact_path": relative_to(workspace.root, artifact_path),
    }


def create_agent_run(
    db_path: Path,
    *,
    job_id: str | None,
    agent_type: str,
    task_type: str,
    provider: str | None = None,
    model: str | None = None,
    prompt_version_id: str | None = None,
    input_refs: list[dict[str, Any]] | None = None,
    status: str = "running",
) -> str:
    run_id = new_id("run")
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, job_id, agent_type, provider, model, task_type, prompt_version_id,
                input_refs_json, output_refs_json, artifact_id, status, started_at, finished_at, error_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', NULL, ?, ?, NULL, NULL)
            """,
            (
                run_id,
                job_id,
                agent_type,
                provider,
                model,
                task_type,
                prompt_version_id,
                json.dumps(input_refs or []),
                status,
                utc_now(),
            ),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def update_agent_run(
    db_path: Path,
    run_id: str,
    *,
    status: str,
    output_refs: list[dict[str, Any]] | None = None,
    artifact_id: str | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    conn = connect(db_path)
    try:
        finished_at = utc_now() if status in {"succeeded", "failed", "blocked", "queued"} else None
        conn.execute(
            """
            UPDATE agent_runs
            SET status = ?,
                output_refs_json = COALESCE(?, output_refs_json),
                artifact_id = COALESCE(?, artifact_id),
                finished_at = COALESCE(?, finished_at),
                error_json = ?
            WHERE id = ?
            """,
            (
                status,
                json.dumps(output_refs) if output_refs is not None else None,
                artifact_id,
                finished_at,
                json.dumps(error) if error is not None else None,
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
