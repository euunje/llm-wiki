from __future__ import annotations

import argparse

from llm_wiki.common import ensure_parent, new_id, relative_to
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.schema import build_empty_candidate_envelope, validate_candidate_envelope
from llm_wiki.workspace import resolve_workspace


PHASE2_NOTE = "Phase 1 placeholder only. Phase 2 implements quality/prompt behavior."


def _ensure_source_exists(db_path, source_id: str) -> None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT id FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown source_id: {source_id}")
    finally:
        conn.close()


def _artifact_target(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value) or "target"


def run_extract_claims(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    _ensure_source_exists(workspace.db, args.source_id)
    job_id = create_job(workspace.db, "extract_claims", target_type="source", target_id=args.source_id)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="phase1_placeholder",
        task_type="extract_claims",
        input_refs=[{"kind": "source", "source_id": args.source_id}],
    )
    envelope = build_empty_candidate_envelope("extract_claims", args.source_id)
    validation = validate_candidate_envelope(envelope)
    payload = {
        "status": "ok" if validation["ok"] else "failed",
        "source_id": args.source_id,
        "job_id": job_id,
        "run_id": run_id,
        "candidate_count": 0,
        "validation": validation,
        "candidate_envelope": envelope,
        "phase_note": PHASE2_NOTE,
    }
    artifact = record_artifact(workspace, "candidate_contract", "extract_claims", payload, "source", args.source_id, run_id)
    update_agent_run(workspace.db, run_id, status="succeeded" if validation["ok"] else "failed", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    update_job(workspace.db, job_id, status="succeeded" if validation["ok"] else "failed", output_refs=[artifact])
    return (0 if validation["ok"] else 1), {**payload, **artifact, "workspace": str(workspace.root), "message": f"Created extract-claims placeholder for {args.source_id}"}


def _placeholder_report(workspace, task_type: str, target: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    job_id = create_job(workspace.db, task_type, target_type="target", target_id=target)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="phase1_placeholder",
        task_type=task_type,
        input_refs=[{"kind": "target", "target": target}],
    )
    body = {"status": "ok", "job_id": job_id, "run_id": run_id, "phase_note": PHASE2_NOTE, **payload}
    artifact = record_artifact(workspace, f"{task_type}_placeholder", task_type, body, "target", _artifact_target(target), run_id)
    update_agent_run(workspace.db, run_id, status="succeeded", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
    return 0, {**body, **artifact, "workspace": str(workspace.root), "message": f"Created {task_type} Phase 1 placeholder"}


def run_summarize(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    return _placeholder_report(
        workspace,
        "summarize",
        args.target,
        {"target": args.target, "summary_placeholder": "Phase 1 placeholder summary.", "source_refs": []},
    )


def run_link(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    return _placeholder_report(
        workspace,
        "link",
        args.target,
        {"target": args.target, "relation_candidates": [], "review_routes": []},
    )


def run_map(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    return _placeholder_report(
        workspace,
        "map",
        args.source_id,
        {"source_id": args.source_id, "mapping_candidates": [], "high_similarity_candidates": []},
    )


def run_ask(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    return _placeholder_report(
        workspace,
        "ask",
        args.query,
        {"query": args.query, "candidates": [], "evidence_refs": [], "answer_placeholder": "Phase 1 placeholder answer."},
    )


def run_compile(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    exit_code, payload = _placeholder_report(
        workspace,
        "compile",
        args.target,
        {"target": args.target, "preview_status": "draft_preview"},
    )
    preview_dir = workspace.artifacts / "compile" / _artifact_target(args.target)
    preview_path = preview_dir / f"{payload['run_id']}.md"
    ensure_parent(preview_path)
    preview_path.write_text(
        "---\n"
        f'title: "{args.target}"\n'
        "aliases: []\n"
        "status: draft_preview\n"
        "source_refs: []\n"
        "claim_refs: []\n"
        "relation_refs: []\n"
        "---\n\n"
        f"# {args.target}\n\n"
        "> Phase 1 placeholder. 실사용 WikiPage 품질은 Phase 2에서 구현한다.\n",
        encoding="utf-8",
    )
    payload["preview_path"] = relative_to(workspace.root, preview_path)
    return exit_code, payload
