from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from llm_wiki.common import utc_now
from llm_wiki.pipeline.section_chunking import SectionChunk
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate
from llm_wiki.slugify import slugify


@dataclass(frozen=True)
class WikiQualityGateResult:
    status: str
    source_common_tags: list[str]
    repairs: list[dict[str, str]]
    issues: list[dict[str, str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_common_tags": self.source_common_tags,
            "repairs": self.repairs,
            "repair_count": len(self.repairs),
            "issues": self.issues,
            "issue_count": len(self.issues),
        }


class WikiQualityGateError(RuntimeError):
    def __init__(self, result: WikiQualityGateResult):
        self.result = result
        super().__init__("wiki generation quality gate failed")


def source_common_tags(source_title: str) -> list[str]:
    slug = slugify(source_title or "source") or "source"
    parts = [part for part in slug.split("-") if part]
    tags: list[str] = []
    if "okf" in parts:
        tags.append("okf")
    elif len(parts) == 1:
        tags.append(parts[0])
    else:
        tags.append(slug)
    source_tag = f"source-{slug}"
    if source_tag not in tags:
        tags.append(source_tag)
    return tags


def repair_and_validate_candidates(
    candidates: list[WikiPageCandidate],
    *,
    source_id: str,
    source_title: str,
    chunks: list[SectionChunk],
) -> tuple[list[WikiPageCandidate], WikiQualityGateResult]:
    common_tags = source_common_tags(source_title)
    repairs: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    fallback_chunk = chunks[0] if chunks else None
    repaired: list[WikiPageCandidate] = []
    for candidate in candidates:
        if not candidate.source_id.strip():
            candidate.source_id = source_id
            repairs.append(_repair(candidate, "set_source_id", source_id))
        if not candidate.summary.strip():
            candidate.summary = f"Source-backed notes for {candidate.title}."
            repairs.append(_repair(candidate, "fill_summary", candidate.summary))
        required_tags = [*common_tags, candidate.node_type]
        before_tags = list(candidate.tags)
        candidate.tags = _unique([*required_tags, *candidate.tags, *candidate.keywords])
        if candidate.tags != before_tags:
            repairs.append(_repair(candidate, "add_common_tags", ",".join(required_tags)))
        if fallback_chunk is not None and not candidate.source_section_refs:
            section_ref = SourceSectionRef(
                chunk_id=f"chunk_{source_id}_{fallback_chunk.chunk_index:03d}",
                heading_path=fallback_chunk.heading_path or (candidate.title,),
                char_start=fallback_chunk.char_start,
                char_end=fallback_chunk.char_end,
            )
            candidate.source_section_refs = [section_ref]
            repairs.append(_repair(candidate, "add_source_section_ref", section_ref.chunk_id))
        if fallback_chunk is not None and not candidate.evidence_claims:
            claim = EvidenceClaim(
                claim_id=f"claim_quality_gate_{candidate.candidate_key}",
                statement=candidate.summary,
                source_id=source_id,
                chunk_id=f"chunk_{source_id}_{fallback_chunk.chunk_index:03d}",
                quote=_quote(fallback_chunk.text),
                char_start=fallback_chunk.char_start,
                char_end=fallback_chunk.char_end,
            )
            candidate.evidence_claims = [claim]
            repairs.append(_repair(candidate, "add_evidence_claim", claim.claim_id))
        if not candidate.draft_body.strip():
            candidate.draft_body = _fallback_body(candidate, fallback_chunk)
            repairs.append(_repair(candidate, "fill_body", candidate.title))
        missing = _candidate_issues(candidate, common_tags)
        issues.extend(missing)
        if not missing:
            repaired.append(candidate)
    status = "failed" if issues else "repaired" if repairs else "ok"
    return repaired, WikiQualityGateResult(status, common_tags, repairs, issues)


def validate_compiled_pages(page_paths: list[Path], *, source_id: str, common_tags: list[str]) -> WikiQualityGateResult:
    issues: list[dict[str, str]] = []
    for path in page_paths:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_markdown(text)
        rel = str(path)
        if not frontmatter:
            issues.append({"page": rel, "issue": "missing_frontmatter"})
        source_ids = frontmatter.get("source_ids") or []
        tags = frontmatter.get("tags") or []
        if source_id not in source_ids:
            issues.append({"page": rel, "issue": "missing_source_id"})
        if not tags:
            issues.append({"page": rel, "issue": "missing_tags"})
        if not set(common_tags).intersection(tags):
            issues.append({"page": rel, "issue": "missing_common_tag"})
        if frontmatter.get("node_type") not in tags:
            issues.append({"page": rel, "issue": "missing_node_type_tag"})
        if not body.strip():
            issues.append({"page": rel, "issue": "empty_body"})
    return WikiQualityGateResult("failed" if issues else "ok", common_tags, [], issues)


def _candidate_issues(candidate: WikiPageCandidate, common_tags: list[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not candidate.source_id.strip():
        issues.append(_issue(candidate, "missing_source_id"))
    if not candidate.tags:
        issues.append(_issue(candidate, "missing_tags"))
    if not set(common_tags).intersection(candidate.tags):
        issues.append(_issue(candidate, "missing_common_tag"))
    if candidate.node_type not in candidate.tags:
        issues.append(_issue(candidate, "missing_node_type_tag"))
    if not candidate.draft_body.strip():
        issues.append(_issue(candidate, "empty_body"))
    if not candidate.source_section_refs:
        issues.append(_issue(candidate, "missing_source_section_refs"))
    return issues


def _fallback_body(candidate: WikiPageCandidate, chunk: SectionChunk | None) -> str:
    lines = [f"# {candidate.title}", "", "## Definition", "", candidate.summary]
    if chunk is not None:
        heading = " > ".join(chunk.heading_path) or candidate.title
        lines.extend([
            "",
            "## Source evidence",
            "",
            f"Derived from `{candidate.source_id}` section `{heading}`.",
            "",
            _quote(chunk.text),
        ])
    return "\n".join(lines).strip() + "\n"


def _quote(text: str) -> str:
    return " ".join(text.split())[:500]


def _unique(items: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        text = str(item).strip().lower()
        if not text:
            continue
        seen.setdefault(text, text)
    return list(seen.values())


def _repair(candidate: WikiPageCandidate, action: str, detail: str) -> dict[str, str]:
    return {"candidate_key": candidate.candidate_key, "title": candidate.title, "action": action, "detail": detail}


def _issue(candidate: WikiPageCandidate, issue: str) -> dict[str, str]:
    return {"candidate_key": candidate.candidate_key, "title": candidate.title, "issue": issue}


def _parse_markdown(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_text = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :]).strip()
            return yaml.safe_load(frontmatter_text) or {}, body
    return {}, text
