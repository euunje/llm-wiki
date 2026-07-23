from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from llm_wiki.common import ensure_parent, new_id, relative_to, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.pipeline.errors import UnsupportedInputError
from llm_wiki.pipeline.hashing import hash_file, hash_text
from llm_wiki.pipeline.wiki_ingest import run_wiki_ingest_pipeline
from llm_wiki.parsers import ParserError, SUPPORTED_EXTENSIONS, parse as parse_document
from llm_wiki.parsers.base import ParsedDocument
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


def _parsed_document_to_markdown(document: ParsedDocument) -> str:
    title = document.title.strip() or document.source_path.stem
    body = document.text.strip()
    if body.startswith("# "):
        return f"{body}\n"
    return f"# {title}\n\n{body}\n"


def _ingest_parsed_document(workspace: WorkspacePaths, path: Path, document: ParsedDocument) -> tuple[dict[str, Any], str]:
    if document.is_empty:
        raise UnsupportedInputError(
            f"No usable text extracted from {path.name}. For scanned/image documents, OCR is required before ingest."
        )
    converted_text = _parsed_document_to_markdown(document)
    content_hash = hash_text(converted_text)
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
        }, content_hash
    raw_name = f"{new_id('raw')}-{_slug(path.stem)}.md"
    raw_path = workspace.raw / raw_name
    ensure_parent(raw_path)
    raw_path.write_text(converted_text, encoding="utf-8")
    metadata = {
        "original_name": path.name,
        "conversion_source": document.file_type,
        "original_bytes": document.bytes,
        "parser_metadata": document.metadata,
    }
    source = _insert_source(
        workspace,
        source_type="converted_markdown",
        title=document.title or path.stem,
        origin=str(path),
        raw_rel_path=relative_to(workspace.root, raw_path),
        content_hash=content_hash,
        metadata=metadata,
    )
    return source, content_hash


def ingest_markdown_file(workspace: WorkspacePaths, input_path: str | Path, *, use_llm: bool = False) -> dict[str, Any]:
    """Ingest a Markdown or HTML file.

    Phase 2 behavior:
    - Markdown files: ingest as-is (existing behavior)
    - HTML files: convert to Markdown first, then ingest
    - Other types (PDF, Office, URL): raise UnsupportedInputError with Phase 2 guidance
    """
    input_str = str(input_path)
    if input_str.startswith(("http://", "https://")):
        record_artifact(
            workspace,
            artifact_type="ingest_conversion_error",
            task_type="ingest",
            payload={
                "status": "error",
                "type": "url_unsupported",
                "reason": "URL ingest is unsupported in Phase 2. Phase 3 will add URL-to-Markdown conversion.",
                "input_kind": "url",
            },
            target_type="source_path",
            target_id="url_input",
        )
        raise UnsupportedInputError(
            "URL ingest is unsupported in Phase 2. Phase 3 will add URL-to-Markdown conversion."
        )
    path = Path(input_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        # Phase 1 behavior: direct Markdown ingest
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
    elif suffix in SUPPORTED_EXTENSIONS:
        try:
            document = parse_document(path)
            source, content_hash = _ingest_parsed_document(workspace, path, document)
            if source.get("status") == "duplicate":
                return source
        except ParserError as exc:
            record_artifact(
                workspace,
                artifact_type="ingest_conversion_error",
                task_type="ingest",
                payload={
                    "status": "error",
                    "type": "parser_error",
                    "reason": str(exc),
                    "path": str(path),
                    "suffix": suffix,
                },
                target_type="source_path",
                target_id=path.name,
            )
            raise UnsupportedInputError(str(exc)) from exc
    else:
        # Unsupported file type
        from llm_wiki.pipeline.hashing import UNSUPPORTED_SUFFIX_GUIDANCE

        if suffix in UNSUPPORTED_SUFFIX_GUIDANCE:
            guidance = UNSUPPORTED_SUFFIX_GUIDANCE[suffix]
        else:
            guidance = f"Unsupported input type '{suffix}'. Supported CLI ingest types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        raise UnsupportedInputError(guidance)
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
    pipeline_payload = run_wiki_ingest_pipeline(workspace, source_id=source["id"], use_llm=use_llm)
    return {
        "status": "ok",
        "source_id": source["id"],
        "job_id": None,
        "source_stub_path": source["stub_path"],
        "raw_path": source["raw_path"],
        "content_hash": content_hash,
        "source_summary_path": pipeline_payload["source_summary_path"],
        "wiki_pages": pipeline_payload["wiki_pages"],
        "page_count": pipeline_payload["page_count"],
        "chunk_count": pipeline_payload["chunk_count"],
        "section_chunk_count": pipeline_payload["section_chunk_count"],
        "quality_gate": pipeline_payload["quality_gate"],
        "llm_page_candidate_attempt": pipeline_payload["llm_page_candidate_attempt"],
        "wiki_artifact_id": pipeline_payload["artifact_id"],
        "wiki_artifact_path": pipeline_payload["artifact_path"],
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


_ARCHIVABLE_INBOX_SUFFIXES = SUPPORTED_EXTENSIONS


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        next_candidate = directory / f"{stem}-{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def _inbox_root_for(file_path: Path) -> Path:
    parent = file_path.parent
    if parent.name in {"_Review", "_Failed"}:
        return parent.parent
    return parent


def _inbox_review_dir_for(file_path: Path) -> Path:
    return _inbox_root_for(file_path) / "_Review"


def _inbox_failed_dir_for(file_path: Path) -> Path:
    return _inbox_root_for(file_path) / "_Failed"


def _inbox_markdown_filename_for(file_path: Path) -> str:
    date_part = utc_now()[:10].replace("-", "")
    return f"{file_path.stem}_{date_part}.md"


def _source_row(workspace: WorkspacePaths, source_id: str) -> dict[str, Any] | None:
    conn = connect(workspace.db)
    try:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _update_source_after_inbox_postprocess(
    workspace: WorkspacePaths,
    *,
    source_id: str,
    original_before: Path,
    original_after: Path,
    markdown_copy: Path,
    update_origin: bool = True,
) -> None:
    conn = connect(workspace.db)
    try:
        row = conn.execute("SELECT metadata_json FROM sources WHERE id = ?", (source_id,)).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}") if row else {}
        metadata["inbox_original_path"] = str(original_before)
        metadata["archived_original_path"] = str(original_after)
        metadata["review_markdown_path"] = str(markdown_copy)
        if update_origin:
            conn.execute(
                "UPDATE sources SET origin = ?, metadata_json = ?, updated_at = ? WHERE id = ?",
                (str(original_after), json.dumps(metadata, ensure_ascii=False, sort_keys=True), utc_now(), source_id),
            )
        else:
            conn.execute(
                "UPDATE sources SET metadata_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(metadata, ensure_ascii=False, sort_keys=True), utc_now(), source_id),
            )
        conn.commit()
    finally:
        conn.close()


def _postprocess_successful_inbox_source(workspace: WorkspacePaths, file_path: Path, result: dict[str, Any]) -> dict[str, Any] | None:
    suffix = file_path.suffix.lower()
    if suffix not in _ARCHIVABLE_INBOX_SUFFIXES or result.get("status") not in {"ok", "duplicate"}:
        return None
    source_id = str(result.get("source_id") or "")
    if not source_id:
        return None
    source_row = _source_row(workspace, source_id)
    raw_rel = result.get("raw_path") or (source_row or {}).get("raw_path")
    if not raw_rel:
        return None
    raw_path = workspace.root / str(raw_rel)
    if not raw_path.exists():
        return {"status": "skipped", "reason": "raw_path_missing", "path": str(raw_path)}

    review_dir = _inbox_review_dir_for(file_path)
    review_dir.mkdir(parents=True, exist_ok=True)
    markdown_copy = _unique_path(review_dir, _inbox_markdown_filename_for(file_path))
    shutil.copy2(raw_path, markdown_copy)

    archive_dir = workspace.data / "inbox_originals"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_original = _unique_path(archive_dir, f"{source_id}-{file_path.name}")
    shutil.move(str(file_path), str(archived_original))
    update_origin = result.get("status") == "ok" or str((source_row or {}).get("origin") or "") == str(file_path)
    _update_source_after_inbox_postprocess(
        workspace,
        source_id=source_id,
        original_before=file_path,
        original_after=archived_original,
        markdown_copy=markdown_copy,
        update_origin=update_origin,
    )
    result["origin"] = str(archived_original)
    result["review_markdown_path"] = str(markdown_copy)
    result["archived_original_path"] = str(archived_original)
    return {
        "status": "ok",
        "source_id": source_id,
        "original_from": str(file_path),
        "original_to": str(archived_original),
        "markdown_to": str(markdown_copy),
    }


def _move_failed_inbox_file(file_path: Path, reason: str, detail: str | None = None) -> dict[str, Any]:
    failed_dir = _inbox_failed_dir_for(file_path)
    failed_dir.mkdir(parents=True, exist_ok=True)
    failed_path = _unique_path(failed_dir, file_path.name)
    if file_path.exists():
        shutil.move(str(file_path), str(failed_path))
    report_path = _unique_path(failed_dir, f"{file_path.stem}_{utc_now()[:10].replace('-', '')}.error.md")
    report = [
        f"# Inbox ingest failed: {file_path.name}",
        "",
        f"- original_path: `{file_path}`",
        f"- moved_to: `{failed_path}`",
        f"- reason: `{reason}`",
    ]
    if detail:
        report.extend(["", "## Detail", "", detail])
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    return {
        "path": str(failed_path),
        "original_path": str(file_path),
        "reason": reason,
        "detail": detail,
        "error_report_path": str(report_path),
    }


def scan_inbox(workspace: WorkspacePaths, scan_paths: list[Path]) -> dict[str, Any]:
    new_sources: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    postprocessed: list[dict[str, Any]] = []
    for scan_path in scan_paths:
        if not scan_path.exists():
            skipped.append({"path": str(scan_path), "reason": "path_not_found"})
            continue
        files = [scan_path] if scan_path.is_file() else sorted(
            p for p in scan_path.iterdir() if p.is_file() and not p.name.startswith(".")
        )
        for file_path in files:
            if file_path.name.startswith("."):
                skipped.append({"path": str(file_path), "reason": "hidden_file"})
                continue
            suffix = file_path.suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                skipped.append(_move_failed_inbox_file(file_path, "unsupported_extension", f"Unsupported suffix: {suffix}"))
                continue
            try:
                result = ingest_markdown_file(workspace, file_path)
            except UnsupportedInputError as exc:
                skipped.append(_move_failed_inbox_file(file_path, "ingest_unsupported", str(exc)))
                continue
            if result["status"] == "duplicate":
                postprocess_result = _postprocess_successful_inbox_source(workspace, file_path, result)
                if postprocess_result:
                    postprocessed.append(postprocess_result)
                duplicates.append(result)
            else:
                postprocess_result = _postprocess_successful_inbox_source(workspace, file_path, result)
                if postprocess_result:
                    postprocessed.append(postprocess_result)
                new_sources.append(result)
    payload = {
        "status": "ok",
        "scanned_paths": [str(path) for path in scan_paths],
        "new_candidate_count": len(new_sources),
        "duplicate_count": len(duplicates),
        "skipped_count": len(skipped),
        "jobs": [item["job_id"] for item in new_sources if item.get("job_id")],
        "sources": [item["source_id"] for item in new_sources],
        "postprocessed": postprocessed,
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
