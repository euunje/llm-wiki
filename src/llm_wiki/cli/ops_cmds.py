from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_wiki.common import ensure_parent, new_id, relative_to, utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect, inspect_database
from llm_wiki.jobs import create_agent_run, record_artifact, update_agent_run
from llm_wiki.search import search_workspace
from llm_wiki.schema import record_human_decision, record_retry_instruction, supersede_candidate, validate_candidate_envelope
from llm_wiki.workspace import resolve_workspace


def _count(conn, query: str, params: tuple[object, ...] = ()) -> int:
    return int(conn.execute(query, params).fetchone()[0])


def run_status(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    conn = connect(workspace.db)
    try:
        summary = {
            "sources": _count(conn, "SELECT COUNT(*) FROM sources"),
            "chunks": _count(conn, "SELECT COUNT(*) FROM source_chunks"),
            "embeddings": _count(conn, "SELECT COUNT(*) FROM embeddings"),
            "jobs_queued": _count(conn, "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"),
            "jobs_failed": _count(conn, "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"),
            "review_pending": _count(conn, "SELECT COUNT(*) FROM review_candidates WHERE status = 'pending'"),
        }
    finally:
        conn.close()
    payload = {"status": "ok", "summary": summary, "workspace": str(workspace.root), "message": "Workspace status summary"}
    return 0, payload


def run_search(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    return 0, search_workspace(workspace, args.query, limit=10, mode="combined")


def run_validate(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    target = args.target
    report = {"status": "ok", "target": target or "workspace", "checks": []}
    exit_code = 0
    if target and target.endswith(".json"):
        path = Path(target) if target.startswith("/") else (workspace.root / target)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            envelope = payload.get("candidate_envelope") if isinstance(payload, dict) else None
            if isinstance(envelope, dict):
                validation = validate_candidate_envelope(envelope)
                report["checks"].append({"kind": "candidate_envelope", **validation})
                if not validation["ok"]:
                    report["status"] = "failed"
                    exit_code = 1
        else:
            report["checks"].append({"kind": "artifact_path", "ok": False, "errors": [f"Artifact not found: {path}"]})
            report["status"] = "failed"
            exit_code = 1
    if not report["checks"]:
        report["checks"].append({"kind": "workspace", "ok": True, "note": "Phase 1 minimal validation report"})
    artifact = record_artifact(workspace, "validation_report", "validate", report, "workspace", "global")
    report.update(artifact)
    report["workspace"] = str(workspace.root)
    report["message"] = "Validation completed"
    return exit_code, report


def run_lint(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    conn = connect(workspace.db)
    try:
        issues = []
        missing_normalized = _count(conn, "SELECT COUNT(*) FROM sources WHERE normalized_path IS NULL OR normalized_path = ''")
        missing_embeddings = _count(conn, "SELECT COUNT(*) FROM source_chunks WHERE embedding_status != 'embedded'")
        failed_jobs = _count(conn, "SELECT COUNT(*) FROM jobs WHERE status = 'failed'")
        if missing_normalized:
            issues.append({"severity": "warn", "rule": "missing_normalized", "count": missing_normalized})
        if missing_embeddings:
            issues.append({"severity": "warn", "rule": "missing_embeddings", "count": missing_embeddings})
        if failed_jobs:
            issues.append({"severity": "warn", "rule": "failed_jobs", "count": failed_jobs})
    finally:
        conn.close()
    payload = {"status": "ok", "issues": issues, "workspace": str(workspace.root), "message": f"Lint found {len(issues)} issue group(s)"}
    return 0, payload


def run_fix(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    conn = connect(workspace.db)
    try:
        rows = conn.execute("SELECT id, title, source_type, pipeline_stage, raw_path, origin, review_status, content_hash, metadata_json FROM sources").fetchall()
    finally:
        conn.close()
    planned = []
    applied = []
    for row in rows:
        stub_path = workspace.wiki_sources / f"{row['id']}.md"
        if not stub_path.exists():
            planned.append({"action": "restore_source_stub", "source_id": row["id"], "path": relative_to(workspace.root, stub_path)})
            if args.apply:
                ensure_parent(stub_path)
                stub_path.write_text(
                    f"---\nsource_id: {row['id']}\ntitle: {json.dumps(row['title'])}\nsource_type: {row['source_type']}\npipeline_stage: {row['pipeline_stage']}\nraw_path: {json.dumps(row['raw_path'])}\norigin: {json.dumps(row['origin'])}\n---\n\n# {row['title']}\n",
                    encoding="utf-8",
                )
                applied.append(planned[-1])
    payload = {"status": "ok", "apply": bool(args.apply), "planned_fixes": planned, "applied_fixes": applied, "workspace": str(workspace.root), "message": "Fix report generated"}
    artifact = record_artifact(workspace, "fix_report", "fix", payload, "workspace", "global")
    payload.update(artifact)
    return 0, payload


def run_retry(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    conn = connect(workspace.db)
    try:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (args.target_id,)).fetchone()
        run = None if job else conn.execute("SELECT * FROM agent_runs WHERE id = ?", (args.target_id,)).fetchone()
        candidate = None if (job or run) else conn.execute("SELECT * FROM review_candidates WHERE id = ?", (args.target_id,)).fetchone()
        if not job and not run and not candidate:
            raise ValueError(f"Unknown job_id/run_id/candidate_id: {args.target_id}")
        record = dict(job or run or candidate)
        target_kind = "job" if job else "run" if run else "candidate"
    finally:
        conn.close()
    retry_id = new_id("retry")
    retry_instruction_id = None
    decision_id = None
    superseded_by = None
    follow_up_run_id = None
    if target_kind == "candidate":
        retry_instruction_id = record_retry_instruction(
            workspace.db,
            args.target_id,
            reason="사용자 retry 요청",
            instruction=args.instruction or "후보를 더 구체적인 근거와 함께 다시 판단",
        )
        decision_id = record_human_decision(
            workspace.db,
            args.target_id,
            "retry_with_instruction",
            note=args.instruction or "후보 재검토 요청",
            retry_instruction_id=retry_instruction_id,
        )
        # Phase 2 CLI keeps retry deterministic and schema-bound: create a new
        # candidate row by copying the old payload and adding retry metadata in
        # related_candidate_keys/review_reason, while human/retry metadata stays
        # in dedicated DB tables.
        old_payload = json.loads(record.get("payload_json") or "{}")
        old_payload["candidate_key"] = old_payload.get("candidate_key", "candidate_01")
        old_payload["review_route"] = old_payload.get("review_route") or "normal_review"
        old_payload["review_reason"] = "retry instruction을 반영한 새 후보입니다."
        related = list(old_payload.get("related_candidate_keys") or [])
        if record.get("candidate_key") and record["candidate_key"] not in related:
            related.append(record["candidate_key"])
        old_payload["related_candidate_keys"] = related
        now = utc_now()
        superseded_by = new_id("candidate")
        follow_up_run_id = create_agent_run(
            workspace.db,
            job_id=None,
            agent_type="phase2_retry_candidate",
            task_type="retry",
            input_refs=[{"kind": "candidate", "candidate_id": args.target_id}],
        )
        conn = connect(workspace.db)
        try:
            conn.execute(
                """
                INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
                """,
                (
                    superseded_by,
                    record["candidate_type"],
                    f"{record['candidate_key']}_retry",
                    record.get("source_id"),
                    follow_up_run_id,
                    json.dumps(old_payload, ensure_ascii=False, sort_keys=True),
                    old_payload["review_route"],
                    old_payload["review_reason"],
                    json.dumps(related, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        supersede_candidate(workspace.db, args.target_id, superseded_by, consumed_run_id=follow_up_run_id)
    payload = {
        "status": "ok",
        "retry_id": retry_id,
        "retry_instruction_id": retry_instruction_id,
        "human_decision_id": decision_id,
        "consumed_run_id": follow_up_run_id,
        "target_kind": target_kind,
        "target_id": args.target_id,
        "previous_status": record.get("status"),
        "instruction": args.instruction or "",
        "superseded_by": superseded_by,
        "phase_note": "Phase 2 records retry metadata in dedicated tables and supersedes candidate rows when target is a candidate.",
        "created_at": utc_now(),
    }
    artifact = record_artifact(workspace, "retry_request", "retry", payload, target_kind, args.target_id)
    if follow_up_run_id:
        update_agent_run(workspace.db, follow_up_run_id, status="succeeded", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    payload.update(artifact)
    payload["workspace"] = str(workspace.root)
    payload["message"] = f"Recorded retry request for {target_kind} {args.target_id}"
    return 0, payload


def run_sync(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    conn = connect(workspace.db)
    try:
        source_count = _count(conn, "SELECT COUNT(*) FROM sources")
        embedding_count = _count(conn, "SELECT COUNT(*) FROM embeddings")
    finally:
        conn.close()
    view_path = workspace.review_candidates / "sync-status.md"
    planned_actions = [{"action": "write_status_view", "path": relative_to(workspace.root, view_path), "reason": "human-readable review status summary"}]
    applied_actions = []
    if args.apply:
        ensure_parent(view_path)
        view_path.write_text(
            f"# Sync Status\n\n- Sources: {source_count}\n- Embeddings: {embedding_count}\n- Generated by wiki sync --apply\n",
            encoding="utf-8",
        )
        applied_actions = planned_actions.copy()
    payload = {
        "status": "ok",
        "apply": bool(args.apply),
        "mode": "apply" if args.apply else "dry_run",
        "planned_actions": planned_actions,
        "applied_actions": applied_actions,
        "summary": {"sources": source_count, "embeddings": embedding_count},
        "workspace": str(workspace.root),
        "message": "Sync report generated",
    }
    artifact = record_artifact(workspace, "sync_report", "sync", payload, "workspace", "global")
    payload.update(artifact)
    return 0, payload


def run_healthcheck(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    lint_exit, lint_payload = run_lint(argparse.Namespace(path=args.path))
    status_exit, status_payload = run_status(argparse.Namespace(path=args.path))
    report = {
        "status": "ok",
        "health": "warn" if lint_payload.get("issues") else "ok",
        "lint": lint_payload,
        "status_summary": status_payload.get("summary"),
        "workspace": str(workspace.root),
        "message": "Healthcheck completed",
    }
    artifact = record_artifact(workspace, "healthcheck_report", "healthcheck", report, "workspace", "global")
    report.update(artifact)
    return (1 if lint_exit or status_exit else 0), report
