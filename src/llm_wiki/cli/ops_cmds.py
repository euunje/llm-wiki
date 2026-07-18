from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_wiki.common import ensure_parent, new_id, relative_to, utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect, inspect_database
from llm_wiki.jobs import record_artifact
from llm_wiki.schema import validate_candidate_envelope
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
    query = (args.query or "").strip()
    if not query:
        return 0, {"status": "ok", "query": "", "results": [], "workspace": str(workspace.root), "message": "No query provided"}
    db_info = inspect_database(workspace.db)
    conn = connect(workspace.db)
    try:
        results = []
        if db_info.get("fts5"):
            rows = conn.execute(
                "SELECT chunk_id, source_id, snippet(source_chunks_fts, 2, '[', ']', '…', 12) AS snippet FROM source_chunks_fts WHERE source_chunks_fts MATCH ? LIMIT 10",
                (query,),
            ).fetchall()
            results.extend({"target_type": "chunk", "target_id": row[0], "source_id": row[1], "snippet": row[2], "match_type": "fts"} for row in rows)
        if not results:
            rows = conn.execute(
                "SELECT id, title FROM sources WHERE title LIKE ? OR metadata_json LIKE ? LIMIT 10",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
            results.extend({"target_type": "source", "target_id": row[0], "title": row[1], "match_type": "metadata"} for row in rows)
    finally:
        conn.close()
    return 0, {"status": "ok", "query": query, "results": results, "workspace": str(workspace.root), "message": f"Found {len(results)} result(s)"}


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
        if not job and not run:
            raise ValueError(f"Unknown job_id/run_id: {args.target_id}")
        record = dict(job or run)
        target_kind = "job" if job else "run"
    finally:
        conn.close()
    retry_id = new_id("retry")
    payload = {
        "status": "ok",
        "retry_id": retry_id,
        "target_kind": target_kind,
        "target_id": args.target_id,
        "previous_status": record.get("status"),
        "instruction": args.instruction or "",
        "phase_note": "Phase 1 records retry request metadata/artifact only; superseded candidate flow is Phase 2.",
        "created_at": utc_now(),
    }
    artifact = record_artifact(workspace, "retry_request", "retry", payload, target_kind, args.target_id)
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
