"""Regression tests for Ja vault Korean-by-default prompt policy."""

from __future__ import annotations

from llm_wiki import prompts, query


def test_ingest_system_prompt_is_korean_by_default():
    assert "in Korean by default" in prompts.SYSTEM_PROMPT
    assert "proper nouns" in prompts.SYSTEM_PROMPT
    assert "code identifiers in English" in prompts.SYSTEM_PROMPT


def test_extraction_prompt_requests_korean_structured_fields():
    assert "source summary" in prompts.EXTRACTION_INSTRUCTIONS
    assert "in Korean by default" in prompts.EXTRACTION_INSTRUCTIONS
    assert "entity descriptions" in prompts.EXTRACTION_INSTRUCTIONS
    assert "concept descriptions" in prompts.EXTRACTION_INSTRUCTIONS


def test_draft_and_source_page_templates_request_korean_body_text():
    assert "Korean section/body text" in prompts.NEW_ENTITY_PAGE_TEMPLATE
    assert "Korean section/body text" in prompts.NEW_CONCEPT_PAGE_TEMPLATE
    assert "Korean section/body text" in prompts.SOURCE_PAGE_TEMPLATE
    assert "## 출처" in prompts.NEW_ENTITY_PAGE_TEMPLATE
    assert "요약" in prompts.SOURCE_PAGE_TEMPLATE


def test_query_prompt_is_korean_by_default():
    assert "Write in Korean by default" in query.SYNTHESIS_SYSTEM_PROMPT
    assert "Korean markdown answer" in query._build_synthesis_user_prompt(
        "token overhead가 뭐야?",
        type("DummyResults", (), {"__len__": lambda self: 0, "hits": []})(),
    )
