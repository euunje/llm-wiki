from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_wiki.common import ensure_parent, new_id, relative_to, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_job, record_artifact, update_job
from llm_wiki.pipeline.hashing import hash_file, hash_text, validate_markdown_input
from llm_wiki.workspace import WorkspacePaths


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return cleaned or "source"


def _fetch_source_by_hash(workspace: WorkspacePaths, content_hash: str) -> dict[str, Any] | None:
    conn = connect(workspace.db)
    try:
        row = conn.execute(
            "SELECT * FROM sources WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _write_source_stub(workspace: WorkspacePaths, source: dict[str, Any]) -> str:
    stub_path = workspace.wiki_sources / f"{source['id']}.md"
    ensure_parent(stub_path)
    metadata = json.loads(source.get("metadata_json") or "{}")
    body = "\n".join(
        [
            "---",
            f"source_id: {source['id']}",
            f"title: {json.dumps(source['title'], ensure_ascii=False)}",
            f"source_type: {source['source_type']}",
            f"pipeline_stage: {source['pipeline_stage']}",
            f"raw_path: {json.dumps(source.get('raw_path'), ensure_ascii=False)}",
            f"origin: {json.dumps(source.get('origin'), ensure_ascii=False)}",
            "---",
            "",
            f"# {source['title']}",
            "",
            f"- Source ID: `{source['id']}`",
            f"- Review status: `{source['review_status']}`",
            f"- Content hash: `{source['content_hash']}`",
            f"- Metadata: `{json.dumps(metadata, ensure_ascii=False, sort_keys=True)}`",
            "",
            "Phase 1 source stub.",
            "",
        ]
    )
    stub_path.write_text(body, encoding="utf-8")
    return relative_to(workspace.root, stub_path)


def _insert_source(
    workspace: WorkspacePaths,
    *,
    source_type: str,
    title: str,
    origin: str,
    raw_rel_path: str,
    content_hash: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    source_id = new_id("source")
    now = utc_now()
    source = {
        "id": source_id,
        "source_type": source_type,
        "title": title,
        "origin": origin,
        "raw_path": raw_rel_path,
        "normalized_path": None,
        "content_hash": content_hash,
        "pipeline_stage": "ingested",
        "review_status": "pending",
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        "created_at": now,
        "updated_at": now,
    }
    conn = connect(workspace.db)
    try:
        conn.execute(
            """
            INSERT INTO sources (
                id, source_type, title, origin, raw_path, normalized_path,
                content_hash, pipeline_stage, review_status, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(source.values()),
        )
        conn.commit()
    finally:
        conn.close()
    source["stub_path"] = _write_source_stub(workspace, source)
    return source


def ingest_markdown_file(workspace: WorkspacePaths, input_path: str | Path) -> dict[str, Any]:
    validate_markdown_input(str(input_path))
    path = Path(input_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    content_hash = hash_file(path)
    duplicate = _fetch_source_by_hash(workspace, content_hash)
    if duplicate:
        return {
            "status": "duplicate",
            "source_id": duplicate["id"],
            "existing_source_id": duplicate["id"],
            "job_id": None,
            "source_stub_path": relative_to(workspace.root, workspace.wiki_sources / f"{duplicate['id']}.md"),
            "content_hash": content_hash,
            "message": f"Duplicate content already ingested as {duplicate['id']}",
        }
    raw_name = f"{new_id('raw')}-{_slug(path.stem)}{path.suffix.lower()}"
    raw_path = workspace.raw / raw_name
    ensure_parent(raw_path)
    raw_path.write_bytes(path.read_bytes())
    source = _insert_source(
        workspace,
        source_type="markdown_file",
        title=path.stem,
        origin=str(path),
        raw_rel_path=relative_to(workspace.root, raw_path),
        content_hash=content_hash,
        metadata={"original_name": path.name},
    )
    # Do NOT create a queued normalize job here — wiki normalize command creates
    # the canonical job. This avoids duplicate normalize jobs for the same source.
    artifact = record_artifact(
        workspace,
        artifact_type="ingest_report",
        task_type="ingest",
        payload={
            "status": "ok",
            "source_id": source["id"],
            "origin": str(path),
            "raw_path": source["raw_path"],
            "content_hash": content_hash,
            "normalize_job_id": None,
            "phase_note": "normalize job is created by explicit wiki normalize command",
        },
        target_type="source",
        target_id=source["id"],
    )
    return {
        "status": "ok",
        "source_id": source["id"],
        "job_id": None,
        "source_stub_path": source["stub_path"],
        "raw_path": source["raw_path"],
        "content_hash": content_hash,
        **artifact,
        "message": f"Ingested Markdown source {source['id']}",
    }


def ingest_text(workspace: WorkspacePaths, title: str, text: str, origin: str = "stdin") -> dict[str, Any]:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Text input is empty")
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Title is required")
    content_hash = hash_text(clean_text)
    duplicate = _fetch_source_by_hash(workspace, content_hash)
    if duplicate:
        return {
            "status": "duplicate",
            "source_id": duplicate["id"],
            "existing_source_id": duplicate["id"],
            "job_id": None,
            "source_stub_path": relative_to(workspace.root, workspace.wiki_sources / f"{duplicate['id']}.md"),
            "content_hash": content_hash,
            "message": f"Duplicate content already ingested as {duplicate['id']}",
        }
    raw_name = f"{new_id('raw')}-{_slug(clean_title)}.md"
    raw_path = workspace.raw / raw_name
    raw_body = f"# {clean_title}\n\n{clean_text}\n"
    ensure_parent(raw_path)
    raw_path.write_text(raw_body, encoding="utf-8")
    source = _insert_source(
        workspace,
        source_type="user_text",
        title=clean_title,
        origin=origin,
        raw_rel_path=relative_to(workspace.root, raw_path),
        content_hash=content_hash,
        metadata={"input_mode": origin},
    )
    # Do NOT create a queued normalize job here — wiki normalize command creates
    # the canonical job. This avoids duplicate normalize jobs for the same source.
    artifact = record_artifact(
        workspace,
        artifact_type="ingest_text_report",
        task_type="ingest_text",
        payload={
            "status": "ok",
            "source_id": source["id"],
            "raw_path": source["raw_path"],
            "content_hash": content_hash,
            "normalize_job_id": None,
            "phase_note": "normalize job is created by explicit wiki normalize command",
        },
        target_type="source",
        target_id=source["id"],
    )
    return {
        "status": "ok",
        "source_id": source["id"],
        "job_id": None,
        "source_stub_path": source["stub_path"],
        "raw_path": source["raw_path"],
        "content_hash": content_hash,
        **artifact,
        "message": f"Ingested text source {source['id']}",
    }


def scan_inbox(workspace: WorkspacePaths, scan_paths: list[Path]) -> dict[str, Any]:
    new_sources: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for scan_path in scan_paths:
        if not scan_path.exists():
            raise FileNotFoundError(f"Inbox path not found: {scan_path}")
        files = [scan_path] if scan_path.is_file() else sorted(
            p for p in scan_path.rglob("*") if p.is_file()
        )
        for file_path in files:
            suffix = file_path.suffix.lower()
            if suffix not in {".md", ".markdown"}:
                skipped.append({"path": str(file_path), "reason": "non_markdown"})
                continue
            result = ingest_markdown_file(workspace, file_path)
            if result["status"] == "duplicate":
                duplicates.append(result)
            else:
                new_sources.append(result)
    payload = {
        "status": "ok",
        "scanned_paths": [str(path) for path in scan_paths],
        "new_candidate_count": len(new_sources),
        "duplicate_count": len(duplicates),
        "skipped_count": len(skipped),
        "jobs": [item["job_id"] for item in new_sources if item.get("job_id")],
        "sources": [item["source_id"] for item in new_sources],
        "duplicates": [{"source_id": item["source_id"]} for item in duplicates],
        "skipped": skipped,
    }
    artifact = record_artifact(
        workspace,
        artifact_type="inbox_scan_report",
        task_type="inbox_scan",
        payload=payload,
        target_type="workspace",
        target_id="global",
    )
    payload.update(artifact)
    payload["message"] = f"Scanned inbox paths; {len(new_sources)} new, {len(duplicates)} duplicates"
    return payload
