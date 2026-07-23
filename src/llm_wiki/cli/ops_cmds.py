from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_wiki.common import ensure_parent, relative_to
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.search import search_workspace
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
