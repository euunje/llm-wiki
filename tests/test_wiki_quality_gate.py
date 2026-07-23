from __future__ import annotations

from pathlib import Path

from llm_wiki.pipeline.section_chunking import SectionChunk
from llm_wiki.pipeline.wiki_quality_gate import repair_and_validate_candidates, source_common_tags
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate


def test_source_common_tags_include_human_topic_and_stable_source_tag() -> None:
    assert source_common_tags("OKF SPEC") == ["okf", "source-okf-spec"]
    assert source_common_tags("Quality Gate Demo") == ["quality-gate-demo", "source-quality-gate-demo"]


def test_quality_gate_repair_is_idempotent_for_existing_common_and_node_type_tags() -> None:
    chunk = SectionChunk(0, ("Frontmatter",), "# Frontmatter\n\nBody text.", 0, 26)
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Frontmatter",
        summary="summary",
        source_id="source_123",
        tags=["okf", "source-okf-spec", "concept"],
        draft_body="# Frontmatter\n\nBody.",
        evidence_claims=[EvidenceClaim("claim_1", "summary", "source_123", "chunk_source_123_000", "Body text.", 0, 26)],
        source_section_refs=[SourceSectionRef("chunk_source_123_000", ("Frontmatter",), 0, 26)],
    )

    repaired, result = repair_and_validate_candidates(
        [candidate],
        source_id="source_123",
        source_title="OKF SPEC",
        chunks=[chunk],
    )

    assert len(repaired) == 1
    assert result.status == "ok"
    assert result.repairs == []
    assert repaired[0].tags.count("okf") == 1
    assert repaired[0].tags.count("source-okf-spec") == 1
    assert repaired[0].tags.count("concept") == 1


def test_quality_gate_reports_failure_when_repair_has_no_source_chunk_for_empty_body() -> None:
    candidate = WikiPageCandidate(
        candidate_key="page_01",
        node_type="concept",
        title="Empty Body",
        summary="summary",
        source_id="source_123",
        tags=["concept"],
        draft_body="",
        source_section_refs=[],
    )

    repaired, result = repair_and_validate_candidates(
        [candidate],
        source_id="source_123",
        source_title="Empty Source",
        chunks=[],
    )

    assert repaired == []
    assert result.status == "failed"
    assert {issue["issue"] for issue in result.issues} >= {"missing_source_section_refs"}
