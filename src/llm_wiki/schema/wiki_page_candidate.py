from __future__ import annotations

from dataclasses import dataclass, field


NODE_TYPES = {
    "concept",
    "method",
    "model",
    "system",
    "project",
    "dataset",
    "person",
    "organization",
    "event",
}


@dataclass(frozen=True)
class SourceSectionRef:
    chunk_id: str
    heading_path: tuple[str, ...]
    char_start: int
    char_end: int


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    statement: str
    source_id: str
    chunk_id: str
    quote: str
    char_start: int
    char_end: int


@dataclass
class WikiPageCandidate:
    candidate_key: str
    node_type: str
    title: str
    summary: str
    source_id: str
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    proposed_frontmatter: dict[str, object] = field(default_factory=dict)
    body_outline: list[str] = field(default_factory=list)
    draft_body: str = ""
    evidence_claims: list[EvidenceClaim] = field(default_factory=list)
    source_section_refs: list[SourceSectionRef] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)


def validate_wiki_page_candidate(candidate: WikiPageCandidate) -> list[str]:
    errors: list[str] = []
    if not candidate.candidate_key:
        errors.append("candidate_key is required")
    if candidate.node_type not in NODE_TYPES:
        errors.append(f"node_type must be one of {sorted(NODE_TYPES)}")
    if not candidate.title.strip():
        errors.append("title is required")
    if not candidate.summary.strip():
        errors.append("summary is required")
    if not candidate.source_id.strip():
        errors.append("source_id is required")
    if not candidate.tags:
        errors.append("tags are required")
    elif candidate.node_type not in {tag.strip().lower() for tag in candidate.tags}:
        errors.append(f"tags must include node_type '{candidate.node_type}'")
    if not candidate.draft_body.strip():
        errors.append("draft_body is required")
    if not candidate.source_section_refs:
        errors.append("source_section_refs is required")
    return errors
