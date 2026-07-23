from __future__ import annotations

from llm_wiki.pipeline.wiki_candidate_merge import merge_wiki_page_candidates
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate


def test_wiki_candidate_merge_combines_duplicate_titles() -> None:
    left = WikiPageCandidate(
        candidate_key="page_a",
        node_type="concept",
        title="Frontmatter",
        summary="Summary A",
        source_id="source_1",
        keywords=["yaml"],
        tags=["metadata"],
        draft_body="A",
        evidence_claims=[EvidenceClaim("claim_a", "A", "source_1", "chunk_a", "quote", 0, 10)],
        source_section_refs=[SourceSectionRef("chunk_a", ("Frontmatter",), 0, 10)],
    )
    right = WikiPageCandidate(
        candidate_key="page_b",
        node_type="concept",
        title="Frontmatter",
        summary="Longer Summary B",
        source_id="source_1",
        keywords=["type"],
        tags=["schema"],
        draft_body="B",
        evidence_claims=[EvidenceClaim("claim_b", "B", "source_1", "chunk_b", "quote", 11, 20)],
        source_section_refs=[SourceSectionRef("chunk_b", ("Frontmatter",), 11, 20)],
    )

    merged = merge_wiki_page_candidates([left, right])

    assert len(merged) == 1
    assert merged[0].summary == "Longer Summary B"
    assert set(merged[0].keywords) == {"yaml", "type"}
    assert len(merged[0].evidence_claims) == 2
