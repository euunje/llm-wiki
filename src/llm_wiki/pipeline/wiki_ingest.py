from __future__ import annotations

import json

import yaml

from llm_wiki.common import relative_to, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.pipeline.chunk import chunk_source
from llm_wiki.pipeline.normalize import normalize_source
from llm_wiki.pipeline.section_chunking import chunk_markdown_by_section
from llm_wiki.pipeline.wiki_candidate_merge import merge_wiki_page_candidates
from llm_wiki.pipeline.wiki_compile import write_compiled_candidates, write_source_summary
from llm_wiki.pipeline.wiki_ingest_llm import extract_wiki_page_candidates_with_optional_llm
from llm_wiki.pipeline.wiki_quality_gate import (
    WikiQualityGateError,
    repair_and_validate_candidates,
    validate_compiled_pages,
)
from llm_wiki.schema.review import insert_candidates_from_envelope
from llm_wiki.schema.wiki_page_candidate import validate_wiki_page_candidate
from llm_wiki.slugify import slugify
from llm_wiki.workspace import WorkspacePaths


def run_wiki_ingest_pipeline(
    workspace: WorkspacePaths,
    *,
    source_id: str,
    use_llm: bool = False,
    persist_review_candidates: bool = False,
    review_run_id: str | None = None,
) -> dict[str, object]:
    normalize_payload = normalize_source(workspace, source_id)
    chunk_payload = chunk_source(workspace, source_id)
    conn = connect(workspace.db)
    try:
        source = dict(conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone())
        chunk_rows = [dict(row) for row in conn.execute("SELECT * FROM source_chunks WHERE source_id = ? ORDER BY chunk_index", (source_id,)).fetchall()]
    finally:
        conn.close()

    normalized_path = workspace.root / str(source["normalized_path"])
    normalized_text = normalized_path.read_text(encoding="utf-8")
    section_chunks = chunk_markdown_by_section(normalized_text)
    candidates, claims_log, llm_page_candidate_attempt = extract_wiki_page_candidates_with_optional_llm(
        workspace,
        source_id=source_id,
        source_title=str(source["title"]),
        chunks=section_chunks,
        use_llm=use_llm,
    )
    merged_candidates = merge_wiki_page_candidates(candidates)
    merged_candidates, quality_gate = repair_and_validate_candidates(
        merged_candidates,
        source_id=source_id,
        source_title=str(source["title"]),
        chunks=section_chunks,
    )
    validation_errors = {
        candidate.candidate_key: validate_wiki_page_candidate(candidate)
        for candidate in merged_candidates
    }
    merged_candidates = [candidate for candidate in merged_candidates if not validation_errors[candidate.candidate_key]]
    if quality_gate.status == "failed" or not merged_candidates:
        failure_payload = {
            "status": "failed",
            "source_id": source_id,
            "stage": "wiki_generation_quality_gate",
            "quality_gate": quality_gate.to_dict(),
            "validation_errors": {key: value for key, value in validation_errors.items() if value},
        }
        record_artifact(
            workspace,
            artifact_type="wiki_quality_gate_failure",
            task_type="wiki_ingest",
            payload=failure_payload,
            target_type="source",
            target_id=source_id,
        )
        raise WikiQualityGateError(quality_gate)
    written_pages = write_compiled_candidates(workspace, merged_candidates)
    persisted_review_candidates: list[dict[str, object]] = []
    if persist_review_candidates:
        persisted_review_candidates = persist_compiled_pages_as_review_candidates(
            workspace,
            source_id=source_id,
            pages=written_pages,
            run_id=review_run_id,
        )
    compiled_quality_gate = validate_compiled_pages(
        [workspace.root / page.path for page in written_pages],
        source_id=source_id,
        common_tags=quality_gate.source_common_tags,
    )
    if compiled_quality_gate.status == "failed":
        failure_payload = {
            "status": "failed",
            "source_id": source_id,
            "stage": "wiki_generation_compiled_quality_gate",
            "quality_gate": compiled_quality_gate.to_dict(),
        }
        record_artifact(
            workspace,
            artifact_type="wiki_quality_gate_failure",
            task_type="wiki_ingest",
            payload=failure_payload,
            target_type="source",
            target_id=source_id,
        )
        raise WikiQualityGateError(compiled_quality_gate)
    quality_gate_payload = quality_gate.to_dict()
    source_slug = slugify(str(source["title"]))
    source_summary_path = write_source_summary(
        workspace,
        source_id=source_id,
        source_title=str(source["title"]),
        source_slug=source_slug,
        origin=str(source.get("origin") or ""),
        raw_path=source.get("raw_path"),
        normalized_path=source.get("normalized_path"),
        page_paths=[page.path for page in written_pages],
        section_titles=[chunk.title for chunk in section_chunks],
    )
    evidence_artifact = record_artifact(
        workspace,
        artifact_type="wiki_claims_evidence",
        task_type="wiki_ingest",
        payload={"source_id": source_id, "claims": claims_log, "use_llm": use_llm},
        target_type="source",
        target_id=source_id,
    )
    pipeline_artifact = record_artifact(
        workspace,
        artifact_type="wiki_ingest_report",
        task_type="wiki_ingest",
        payload={
            "status": "ok",
            "source_id": source_id,
            "normalized_path": normalize_payload["normalized_path"],
            "chunk_count": chunk_payload["chunk_count"],
            "section_chunk_count": len(section_chunks),
            "page_count": len(written_pages),
            "pages": [page.__dict__ for page in written_pages],
            "persisted_review_candidates": persisted_review_candidates,
            "source_summary_path": source_summary_path,
            "validation_errors": {key: value for key, value in validation_errors.items() if value},
            "quality_gate": quality_gate_payload,
            "llm_page_candidate_attempt": llm_page_candidate_attempt.to_dict(),
            "evidence_artifact_id": evidence_artifact["artifact_id"],
        },
        target_type="source",
        target_id=source_id,
    )
    _replace_source_stub_with_summary(workspace, source_id, source_summary_path)
    return {
        "status": "ok",
        "source_id": source_id,
        "normalized_path": normalize_payload["normalized_path"],
        "chunk_count": chunk_payload["chunk_count"],
        "section_chunk_count": len(section_chunks),
        "page_count": len(written_pages),
        "wiki_pages": [page.__dict__ for page in written_pages],
        "persisted_review_candidates": persisted_review_candidates,
        "source_summary_path": source_summary_path,
        "quality_gate": quality_gate_payload,
        "llm_page_candidate_attempt": llm_page_candidate_attempt.to_dict(),
        "evidence_artifact": evidence_artifact,
        **pipeline_artifact,
    }


def _split_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown
    lines = markdown.splitlines()
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = yaml.safe_load("\n".join(lines[1:index])) or {}
            body = "\n".join(lines[index + 1 :]).lstrip("\n")
            return (frontmatter if isinstance(frontmatter, dict) else {}), body
    return {}, markdown


def persist_compiled_pages_as_review_candidates(
    workspace: WorkspacePaths,
    *,
    source_id: str,
    pages: list[CompiledPage],
    run_id: str | None = None,
) -> list[dict[str, object]]:
    """Expose compiled wiki page drafts to the Mapping UI via review_candidates."""
    conn = connect(workspace.db)
    try:
        conn.execute(
            """
            UPDATE review_candidates
            SET status = 'superseded', updated_at = ?
            WHERE source_id = ? AND status = 'pending'
              AND candidate_type IN ('node', 'claim', 'mapping', 'relation', 'claim_conflict')
            """,
            (utc_now(), source_id),
        )
        conn.commit()
    finally:
        conn.close()

    node_candidates: list[dict[str, object]] = []
    for page in pages:
        page_path = workspace.root / page.path
        markdown = page_path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(markdown)
        title = str(frontmatter.get("title") or page.title)
        node_type = str(frontmatter.get("node_type") or "concept")
        tags = frontmatter.get("tags") if isinstance(frontmatter.get("tags"), list) else []
        aliases = frontmatter.get("aliases") if isinstance(frontmatter.get("aliases"), list) else []
        node_candidates.append(
            {
                "candidate_key": f"wiki_page_{page.slug}",
                "node_type": node_type,
                "title": title,
                "aliases": aliases,
                "summary": str(frontmatter.get("summary") or ""),
                "tags": tags,
                "body": body,
                "frontmatter": frontmatter,
                "source_id": source_id,
                "source_path": page.path,
                "compiled_node_id": page.node_id,
                "review_route": "normal_review",
                "review_reason": "문서 타입별 wiki page 생성 파이프라인에서 만든 고품질 페이지 후보입니다.",
                "related_candidate_keys": [],
            }
        )
    if not node_candidates:
        return []
    return insert_candidates_from_envelope(
        workspace.db,
        {
            "task_type": "wiki_page_mapping",
            "source_id": source_id,
            "schema_version": "candidate.v1",
            "claim_candidates": [],
            "node_candidates": node_candidates,
            "relation_candidates": [],
            "mapping_candidates": [],
            "claim_conflict_candidates": [],
        },
        run_id,
    )


def _replace_source_stub_with_summary(workspace: WorkspacePaths, source_id: str, source_summary_path: str) -> None:
    stub_path = workspace.wiki_sources / f"{source_id}.md"
    if not stub_path.exists():
        return
    summary_path = workspace.root / source_summary_path
    stub_path.write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")
