from __future__ import annotations

from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate, validate_wiki_page_candidate


def test_wiki_page_candidate_validator_accepts_source_backed_candidate() -> None:
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Frontmatter",
        summary="YAML metadata block at the top of a markdown concept document.",
        source_id="source_123",
        keywords=["yaml", "frontmatter"],
        tags=["metadata", "concept"],
        draft_body="# Frontmatter\n\n## Definition\n\nYAML metadata block.",
        evidence_claims=[EvidenceClaim("claim_1", "Frontmatter is YAML metadata.", "source_123", "chunk_1", "YAML frontmatter block", 0, 20)],
        source_section_refs=[SourceSectionRef("chunk_1", ("Concept Documents", "Frontmatter"), 0, 40)],
    )

    assert validate_wiki_page_candidate(candidate) == []


def test_wiki_page_candidate_validator_rejects_missing_source_refs() -> None:
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Frontmatter",
        summary="summary",
        source_id="source_123",
        keywords=["yaml"],
    )

    errors = validate_wiki_page_candidate(candidate)
    assert "source_section_refs is required" in errors
    assert "tags are required" in errors
    assert "draft_body is required" in errors


def test_wiki_page_candidate_validator_rejects_tags_without_node_type() -> None:
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Frontmatter",
        summary="summary",
        source_id="source_123",
        tags=["metadata"],
        draft_body="# Frontmatter\n\nBody.",
        source_section_refs=[SourceSectionRef("chunk_1", ("Frontmatter",), 0, 20)],
    )

    errors = validate_wiki_page_candidate(candidate)
    assert "tags must include node_type 'concept'" in errors
