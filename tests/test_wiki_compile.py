from __future__ import annotations

from llm_wiki.pipeline.wiki_compile import compile_candidate_markdown
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate


def test_wiki_compile_outputs_ontology_aligned_frontmatter() -> None:
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Conformance",
        summary="Conditions for a bundle to conform.",
        source_id="source_123",
        keywords=["conformance"],
        tags=["rules"],
        draft_body="# Conformance\n\n## Definition\n\nConditions for a bundle to conform.",
        evidence_claims=[EvidenceClaim("claim_1", "A bundle is conformant if...", "source_123", "chunk_1", "A bundle is conformant", 0, 20)],
        source_section_refs=[SourceSectionRef("chunk_1", ("Conformance",), 0, 20)],
    )

    slug, node_id, markdown = compile_candidate_markdown(candidate)

    assert slug == "conformance"
    assert node_id == "concept-conformance"
    assert "record_type: knowledge_node" in markdown
    assert "node_type: concept" in markdown
    assert "claim_ids:" in markdown
    assert "# Conformance" in markdown
