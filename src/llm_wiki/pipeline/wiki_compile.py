from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from llm_wiki.common import ensure_parent, relative_to, utc_now
from llm_wiki.schema.wiki_page_candidate import WikiPageCandidate
from llm_wiki.slugify import slugify
from llm_wiki.workspace import WorkspacePaths


@dataclass(frozen=True)
class CompiledPage:
    title: str
    slug: str
    node_id: str
    path: str


def compile_candidate_markdown(candidate: WikiPageCandidate) -> tuple[str, str, str]:
    slug = slugify(candidate.title)
    node_id = f"{candidate.node_type}-{slug}"
    now = utc_now()
    frontmatter = {
        "id": node_id,
        "record_type": "knowledge_node",
        "node_type": candidate.node_type,
        "title": candidate.title,
        "aliases": candidate.aliases,
        "summary": candidate.summary,
        "node_state": "draft",
        "schema_version": 1,
        "created_at": now,
        "updated_at": now,
        "created_by": "import",
        "source_ids": [candidate.source_id],
        "claim_ids": [claim.claim_id for claim in candidate.evidence_claims],
        "merged_from": candidate.merged_from,
        "tags": candidate.tags,
        "relations": [],
    }
    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    body = candidate.draft_body.strip() or f"# {candidate.title}\n\n{candidate.summary}\n"
    return slug, node_id, f"---\n{yaml_text}\n---\n\n{body}\n"


def write_compiled_candidates(workspace: WorkspacePaths, candidates: list[WikiPageCandidate]) -> list[CompiledPage]:
    written: list[CompiledPage] = []
    for candidate in candidates:
        slug, node_id, markdown = compile_candidate_markdown(candidate)
        page_path = workspace.wiki_concepts / f"{slug}.md"
        ensure_parent(page_path)
        page_path.write_text(markdown, encoding="utf-8")
        written.append(CompiledPage(candidate.title, slug, node_id, relative_to(workspace.root, page_path)))
    return written


def write_source_summary(
    workspace: WorkspacePaths,
    *,
    source_id: str,
    source_title: str,
    source_slug: str,
    origin: str,
    raw_path: str | None,
    normalized_path: str | None,
    page_paths: list[str],
    section_titles: list[str],
) -> str:
    summary_path = workspace.wiki_sources / f"{source_slug}.md"
    frontmatter = {
        "id": source_id,
        "record_type": "source",
        "source_type": "markdown",
        "title": source_title,
        "origin": {"path": origin},
        "raw_path": raw_path,
        "normalized_path": normalized_path,
        "source_state": "active",
        "schema_version": 1,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    lines = [
        "---",
        yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip(),
        "---",
        "",
        f"# {source_title}",
        "",
        "## Summary",
        "",
        f"Generated wiki pages: {len(page_paths)}.",
        "",
        "## Covered sections",
        "",
        *[f"- {title}" for title in section_titles],
        "",
        "## Generated pages",
        "",
        *[f"- [[{path.removeprefix('vault/10_Wiki/').removesuffix('.md')}]]" for path in page_paths],
        "",
    ]
    ensure_parent(summary_path)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return relative_to(workspace.root, summary_path)
