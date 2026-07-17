"""Regression tests for the 2-pass JSON page generation and validation pipeline.

Verifies:
- ``_parse_generated_page`` accepts valid GeneratedPage JSON and rejects malformed
  responses with ``ValueError`` so the caller can fall back to the retry path.
- ``_validate_generated_page`` enforces the structured page contract:
    * disallowed ``links_used`` (links not in the per-page allowed set)
    * ``links_used`` mismatch with the wikilinks actually present in ``body_markdown``
    * required ``sources/<source_slug>.md`` entry in ``sources``
    * matching ``slug`` and ``type`` fields
    * non-empty ``body_markdown``
- End-to-end ``ingest_source`` flow:
    * Invalid JSON on the first ``chat_stream`` call is retried via ``chat`` and
      a valid response is written to the correct page directory.
    * Invalid JSON that survives the retry is routed to ``non_categories/`` as a
      ``pageKind: review`` item whose ``reason`` surfaces the validation errors.

The tests use deterministic fake LLM clients; no network or real model is invoked.
"""

from __future__ import annotations

import json
import yaml

from llm_wiki import config as cfg
from llm_wiki import db
from llm_wiki.ingest_llm import (
    GeneratedPage,
    IngestCallbacks,
    _parse_generated_page,
    _validate_generated_page,
    ingest_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ja_runtime_config(vault_root, runtime, raw_dir="10. Raw Sources"):
    """Build the standard Ja layout runtime config used by ingest tests."""
    runtime.mkdir(parents=True, exist_ok=True)
    config = {
        "paths": {
            "root": str(vault_root),
            "raw_dir": raw_dir,
            "internal_dir": str(runtime),
            "wiki_dir": "20. Wiki",
            "page_dirs": {
                "sources": "20. Wiki/20. Sources",
                "entities": "20. Wiki/22. Entities",
                "concepts": "20. Wiki/21. Concepts",
                "synthesis": "30. Queries",
                "non_categories": "00. Inbox/_Review",
            },
            "files": {"state_db": str(runtime / "state.sqlite")},
        }
    }
    runtime_config = runtime / "config.yml"
    runtime_config.write_text(yaml.safe_dump(config), encoding="utf-8")
    return runtime_config


def _register_markdown_source(paths, relpath, text):
    source_path = paths.root / relpath
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(text, encoding="utf-8")
    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            """
            INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (relpath, f"hash-{relpath}", "markdown", source_path.stat().st_size, "2026-07-15T00:00:00Z", "pending"),
        )
        return conn.execute("SELECT id FROM sources ORDER BY id DESC LIMIT 1").fetchone()[0]


def _valid_entity_json(source_slug: str = "two-pass-source", slug: str = "openai") -> str:
    return json.dumps(
        {
            "slug": slug,
            "type": "entity",
            "body_markdown": (
                f"# OpenAI\n\n"
                f"OpenAI is an AI research company.\n\n"
                f"## 출처\n\n"
                f"[[sources/{source_slug}]]\n"
            ),
            "links_used": [f"sources/{source_slug}"],
            "sources": [f"sources/{source_slug}.md"],
        }
    )


# ---------------------------------------------------------------------------
# Tests: _parse_generated_page
# ---------------------------------------------------------------------------


def test_parse_generated_page_accepts_valid_json():
    raw = _valid_entity_json()
    generated = _parse_generated_page(raw)
    assert isinstance(generated, GeneratedPage)
    assert generated.slug == "openai"
    assert generated.type == "entity"
    assert generated.sources == ["sources/two-pass-source.md"]
    assert "## 출처" in generated.body_markdown


def test_parse_generated_page_strips_markdown_fences():
    raw = "```json\n" + _valid_entity_json() + "\n```"
    generated = _parse_generated_page(raw)
    assert generated.slug == "openai"


def test_parse_generated_page_repairs_invalid_string_escapes_only():
    raw = json.dumps(
        {
            "slug": "openai",
            "type": "entity",
            "body_markdown": "Path C:\\Users\\name\\project\\foo\\_bar\n\t[[sources/two-pass-source]]",
            "links_used": ["sources/two-pass-source"],
            "sources": ["sources/two-pass-source.md"],
        }
    ).replace("\\\\_bar", "\\_bar")

    generated = _parse_generated_page(raw)

    assert generated.body_markdown == "Path C:\\Users\\name\\project\\foo\\_bar\n\t[[sources/two-pass-source]]"


def test_parse_generated_page_rejects_invalid_json():
    import pytest

    with pytest.raises(ValueError) as exc_info:
        _parse_generated_page("not a json object at all")
    assert "Invalid page JSON" in str(exc_info.value)


def test_parse_generated_page_rejects_schema_mismatch():
    """JSON that parses but doesn't match GeneratedPage contract must raise."""
    import pytest

    raw = json.dumps({"slug": "openai"})  # missing required fields
    with pytest.raises(ValueError) as exc_info:
        _parse_generated_page(raw)
    assert "schema" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests: _validate_generated_page — disallowed links
# ---------------------------------------------------------------------------


def test_validate_generated_page_flags_disallowed_links():
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "See [[entities/openai]] and [[entities/secret-third-party]].\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        links_used=["entities/openai", "entities/secret-third-party"],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=[
            "sources/two-pass-source",
            "entities/openai",
            "concepts/rag",
        ],
        source_slug="two-pass-source",
    )
    assert any("disallowed" in err for err in errors), errors
    assert any("entities/secret-third-party" in err for err in errors), errors


def test_validate_generated_page_accepts_only_allowed_links():
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "See [[entities/openai]] and [[concepts/rag]].\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        links_used=["entities/openai", "concepts/rag", "sources/two-pass-source"],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=[
            "sources/two-pass-source",
            "entities/openai",
            "concepts/rag",
        ],
        source_slug="two-pass-source",
    )
    assert errors == []


# ---------------------------------------------------------------------------
# Tests: _validate_generated_page — links_used mismatch with body
# ---------------------------------------------------------------------------


def test_validate_generated_page_flags_links_used_mismatch_missing():
    """A wikilink in body that is not declared in links_used is a mismatch."""
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "See [[concepts/rag]] for context.\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        # links_used omits concepts/rag
        links_used=["sources/two-pass-source"],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=[
            "sources/two-pass-source",
            "entities/openai",
            "concepts/rag",
        ],
        source_slug="two-pass-source",
    )
    assert any("links_used must exactly match" in err for err in errors), errors


def test_validate_generated_page_flags_links_used_mismatch_extra():
    """A link in links_used that does not appear in body is a mismatch."""
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "OpenAI builds AI models.\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        # links_used declares concepts/rag but body has no such wikilink
        links_used=["sources/two-pass-source", "concepts/rag"],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=[
            "sources/two-pass-source",
            "entities/openai",
            "concepts/rag",
        ],
        source_slug="two-pass-source",
    )
    assert any("links_used must exactly match" in err for err in errors), errors


# ---------------------------------------------------------------------------
# Tests: _validate_generated_page — sources must include the source page
# ---------------------------------------------------------------------------


def test_validate_generated_page_requires_source_reference():
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "OpenAI builds AI models.\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        links_used=["sources/two-pass-source"],
        sources=[],  # missing the required source
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=["sources/two-pass-source", "entities/openai"],
        source_slug="two-pass-source",
    )
    assert any("sources must include" in err for err in errors), errors
    assert any("sources/two-pass-source.md" in err for err in errors), errors


def test_validate_generated_page_accepts_source_reference_with_aliases():
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown=(
            "# OpenAI\n\n"
            "OpenAI builds AI models.\n\n"
            "## 출처\n\n"
            "[[sources/two-pass-source]]\n"
        ),
        links_used=["sources/two-pass-source"],
        sources=[
            "sources/old-source.md",
            "sources/two-pass-source.md",
        ],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=["sources/two-pass-source", "entities/openai"],
        source_slug="two-pass-source",
    )
    assert errors == []


# ---------------------------------------------------------------------------
# Tests: _validate_generated_page — slug / type / body invariants
# ---------------------------------------------------------------------------


def test_validate_generated_page_rejects_wrong_slug():
    generated = GeneratedPage(
        slug="different-slug",
        type="entity",
        body_markdown="# different-slug\n\nBody.",
        links_used=[],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=["sources/two-pass-source"],
        source_slug="two-pass-source",
    )
    assert any("slug must be 'openai'" in err for err in errors), errors


def test_validate_generated_page_rejects_wrong_type():
    generated = GeneratedPage(
        slug="openai",
        type="concept",
        body_markdown="# OpenAI\n\nOpenAI is a concept.",
        links_used=[],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=["sources/two-pass-source"],
        source_slug="two-pass-source",
    )
    assert any("type must be 'entity'" in err for err in errors), errors


def test_validate_generated_page_rejects_empty_body():
    generated = GeneratedPage(
        slug="openai",
        type="entity",
        body_markdown="   \n\n  ",
        links_used=[],
        sources=["sources/two-pass-source.md"],
    )
    errors = _validate_generated_page(
        generated,
        expected_slug="openai",
        expected_type="entity",
        allowed_links=["sources/two-pass-source"],
        source_slug="two-pass-source",
    )
    assert any("body_markdown must be non-empty" in err for err in errors), errors


# ---------------------------------------------------------------------------
# End-to-end: invalid first response is retried successfully
# ---------------------------------------------------------------------------


class _InvalidThenValidEntityClient:
    """Fake LLM that returns an invalid page JSON on the first stream attempt
    and a valid page JSON on the retry (non-streaming) call.

    Records call counts so the test can assert the retry actually happened.
    """

    provider = "ollama"

    def __init__(self, source_slug: str = "retry-success-source", slug: str = "openai"):
        self.source_slug = source_slug
        self.slug = slug
        self.stream_calls = 0
        self.retry_calls = 0

    EXTRACTION_JSON = """{
  "title": "Retry Success Source",
  "source_slug": "retry-success-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}"""

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        # Extraction pass
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        # Retry of an invalid structured page response
        if "이전 응답은 페이지 JSON" in prompt or "JSON 계약" in prompt:
            self.retry_calls += 1
            return json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": (
                        f"# OpenAI\n\n"
                        f"OpenAI is an AI research company.\n\n"
                        f"## 출처\n\n"
                        f"[[sources/{self.source_slug}]]\n"
                    ),
                    "links_used": [f"sources/{self.source_slug}"],
                    "sources": [f"sources/{self.source_slug}.md"],
                }
            )
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            # Source page: legacy markdown (no JSON template used)
            text = (
                "---\n"
                "title: Retry Success Source\n"
                "type: source\n"
                "tags: [ai]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# Retry Success Source\n\n"
                "Source summary.\n"
            )
        else:
            # Entity page: first attempt is intentionally invalid.
            # The body declares a wikilink that is NOT in links_used,
            # so the validator will reject it and trigger a retry.
            self.stream_calls += 1
            text = json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": (
                        f"# OpenAI\n\n"
                        f"See [[concepts/rag]] for context.\n\n"
                        f"## 출처\n\n"
                        f"[[sources/{self.source_slug}]]\n"
                    ),
                    # links_used is missing concepts/rag → validator rejects
                    "links_used": [f"sources/{self.source_slug}"],
                    "sources": [f"sources/{self.source_slug}.md"],
                }
            )
        if False:
            yield ""
        return text


def test_invalid_first_response_is_retried_and_succeeds(tmp_path, monkeypatch):
    """First chat_stream returns invalid page JSON (links_used mismatch).
    The validator triggers a retry via chat(), which returns valid JSON.
    The entity page is then written to the configured entities directory.

    Note: this test uses the default ``<root>/.wiki/config.yml`` location
    (no ``LLM_WIKI_CONFIG`` env override) to avoid a config-overwrite side
    effect inside ``_build_staged_lint_paths`` that is independent of the
    STAB-002 retry fix being verified here.
    """
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    paths, _ = _setup_internal_wiki(tmp_path)
    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/retry-success.md",
        "# Retry Success\n\nOpenAI builds AI models.",
    )

    client = _InvalidThenValidEntityClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # Retry path was exercised
    assert client.stream_calls == 1, "expected one invalid stream attempt"
    assert client.retry_calls == 1, "expected exactly one retry call"

    # Ingest succeeded
    assert result.ok, f"ingest failed: {result.error}"
    assert result.error is None

    # Entity page landed in the entities directory, NOT in non_categories
    entity_path = vault_root / "20. Wiki/22. Entities/openai.md"
    assert entity_path.exists(), "entity page should be in entities/"
    assert not (vault_root / "00. Inbox/_Review/openai.md").exists(), (
        "entity page should NOT be in non_categories/ after a successful retry"
    )

    content = entity_path.read_text(encoding="utf-8")
    assert "type: entity" in content
    assert "[[sources/retry-success-source]]" in content
    # Source page is still written
    assert (vault_root / "20. Wiki/20. Sources/retry-success-source.md").exists()

    kinds = {change.kind for change in result.changes}
    assert "entity" in kinds
    assert "source" in kinds
    assert "review" not in kinds


# ---------------------------------------------------------------------------
# End-to-end: invalid response that survives the retry is routed to review
# ---------------------------------------------------------------------------


class _AlwaysInvalidEntityClient:
    """Fake LLM that returns an invalid page JSON on the first stream attempt
    AND an invalid page JSON on the retry. The validator should give up and
    the entity should be staged as a review candidate in non_categories/.
    """

    provider = "ollama"

    def __init__(self, source_slug: str = "retry-fail-source", slug: str = "openai"):
        self.source_slug = source_slug
        self.slug = slug
        self.stream_calls = 0
        self.retry_calls = 0

    EXTRACTION_JSON = """{
  "title": "Retry Fail Source",
  "source_slug": "retry-fail-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}"""

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        if "이전 응답은 페이지 JSON" in prompt or "JSON 계약" in prompt:
            self.retry_calls += 1
            # Still invalid: same body but links_used still mismatched
            return json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": (
                        f"# OpenAI\n\n"
                        f"See [[concepts/rag]] for context.\n\n"
                        f"## 출처\n\n"
                        f"[[sources/{self.source_slug}]]\n"
                    ),
                    # Still missing concepts/rag
                    "links_used": [f"sources/{self.source_slug}"],
                    "sources": [f"sources/{self.source_slug}.md"],
                }
            )
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            text = (
                "---\n"
                "title: Retry Fail Source\n"
                "type: source\n"
                "tags: [ai]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# Retry Fail Source\n\n"
                "Source summary.\n"
            )
        else:
            self.stream_calls += 1
            # Invalid: missing required source entry
            text = json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": "# OpenAI\n\nOpenAI is a company.",
                    "links_used": [],
                    "sources": [],
                }
            )
        if False:
            yield ""
        return text


def test_invalid_page_after_retry_becomes_review_non_categories(tmp_path, monkeypatch):
    """Both the first stream and the retry produce invalid page JSON. The
    entity should be staged as a review candidate under non_categories/
    with a reason that captures the validation errors.

    Note: this test uses the default ``<root>/.wiki/config.yml`` location
    (no ``LLM_WIKI_CONFIG`` env override) to avoid a config-overwrite side
    effect inside ``_build_staged_lint_paths`` that is independent of the
    STAB-002 retry fix being verified here.
    """
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    paths, _ = _setup_internal_wiki(tmp_path)
    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/retry-fail.md",
        "# Retry Fail\n\nOpenAI builds AI models.",
    )

    client = _AlwaysInvalidEntityClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # Both attempts happened
    assert client.stream_calls == 1
    assert client.retry_calls == 1

    # Ingest finished without a hard error; the entity was diverted to review
    assert result.ok, f"ingest failed: {result.error}"
    kinds = {change.kind for change in result.changes}
    assert "review" in kinds, f"expected a review change, got {kinds}"

    # Entity directory is empty; review file lives in non_categories/
    assert not (vault_root / "20. Wiki/22. Entities/openai.md").exists()
    review_path = vault_root / "00. Inbox/_Review/openai.md"
    assert review_path.exists(), "entity should be staged as a review item"

    content = review_path.read_text(encoding="utf-8")
    assert "pageKind: review" in content
    assert "type: review" in content
    assert "status: pending_review" in content
    # Validation errors should be surfaced in the reason field
    assert "Reason" in content
    # Either "disallowed", "links_used", or "sources" should be referenced
    assert any(
        marker in content
        for marker in ("disallowed", "links_used", "sources must include", "body_markdown")
    ), f"review reason should reference validation errors: {content!r}"

    # Source page is still written
    assert (vault_root / "20. Wiki/20. Sources/retry-fail-source.md").exists()


# ---------------------------------------------------------------------------
# Regression tests for STAB-002 (prose-only response retries to a clean JSON
# page) and STAB-003 (stream callback exceptions are not silently swallowed).
#
# These tests intentionally use the default ``<root>/.wiki/config.yml`` config
# location rather than the ``LLM_WIKI_CONFIG`` env override. That keeps the
# staged lint config from clobbering the runtime config during
# ``_build_staged_lint_paths`` — an orthogonal issue not covered by STAB-002/003.
# ---------------------------------------------------------------------------


def _setup_internal_wiki(tmp_path):
    """Write a Ja-layout runtime config to ``<vault_root>/.wiki/config.yml``.

    Returns ``(paths, config_path)``. ``LLM_WIKI_CONFIG`` is intentionally NOT
    set so that the lint staging config does not overwrite the runtime config.
    """
    vault_root = tmp_path / "vault"
    config_dir = vault_root / ".wiki"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "paths": {
            "root": str(vault_root),
            "raw_dir": "10. Raw Sources",
            "internal_dir": str(config_dir),
            "wiki_dir": "20. Wiki",
            "page_dirs": {
                "sources": "20. Wiki/20. Sources",
                "entities": "20. Wiki/22. Entities",
                "concepts": "20. Wiki/21. Concepts",
                "synthesis": "30. Queries",
                "non_categories": "00. Inbox/_Review",
            },
            "files": {"state_db": str(config_dir / "state.sqlite")},
        }
    }
    config_path = config_dir / "config.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return cfg.WikiPaths(vault_root), config_path


class _ProseThenValidEntityClient:
    """Fake LLM client where the first ``chat_stream`` for the entity page
    returns pure prose (no JSON at all). The retry path through ``chat`` returns
    a fully valid page JSON, so STAB-002's retry-on-parse-failure fix should
    successfully produce the entity page in ``entities/`` (NOT
    ``non_categories/``)."""

    provider = "ollama"

    def __init__(
        self,
        source_slug: str = "retry-prose-source",
        slug: str = "openai",
    ):
        self.source_slug = source_slug
        self.slug = slug
        self.stream_calls = 0
        self.retry_calls = 0

    EXTRACTION_JSON = """{
  "title": "Retry Prose Source",
  "source_slug": "retry-prose-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}"""

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        if "이전 응답은 페이지 JSON" in prompt or "JSON 계약" in prompt:
            # Retry path: emit a fully valid GeneratedPage JSON this time.
            self.retry_calls += 1
            return json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": (
                        f"# OpenAI\n\n"
                        f"OpenAI is an AI research company.\n\n"
                        f"## 출처\n\n"
                        f"[[sources/{self.source_slug}]]\n"
                    ),
                    "links_used": [f"sources/{self.source_slug}"],
                    "sources": [f"sources/{self.source_slug}.md"],
                }
            )
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            text = (
                "---\n"
                "title: Retry Prose Source\n"
                "type: source\n"
                "tags: [ai]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# Retry Prose Source\n\n"
                "Source summary.\n"
            )
        else:
            # First entity attempt: pure prose, no JSON object at all.
            # _parse_generated_page will raise ValueError; the retry path
            # should take over via chat().
            self.stream_calls += 1
            text = (
                "I am unable to format the response as JSON right now. "
                "OpenAI is an AI research company based in San Francisco. "
                "It was founded in 2015."
            )
        if False:
            yield ""
        return text


def test_stab002_prose_first_response_retries_and_succeeds(tmp_path, monkeypatch):
    """STAB-002: ``chat_stream`` returns pure prose on the first attempt (no
    JSON). The retry through non-stream ``chat`` returns valid page JSON, and
    the ingest must land the entity page in ``entities/`` (NOT
    ``non_categories/``)."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths, _ = _setup_internal_wiki(tmp_path)
    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/retry-prose.md",
        "# Retry Prose\n\nOpenAI details.",
    )

    client = _ProseThenValidEntityClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # Retry path was actually exercised.
    assert client.stream_calls == 1, "expected one prose-only stream attempt"
    assert client.retry_calls == 1, "expected exactly one retry via chat()"

    # Ingest succeeded.
    assert result.ok, f"ingest failed: {result.error}"
    assert result.error is None

    # Entity page landed in entities/, NOT in non_categories/.
    vault_root = tmp_path / "vault"
    entity_path = vault_root / "20. Wiki/22. Entities/openai.md"
    review_path = vault_root / "00. Inbox/_Review/openai.md"
    assert entity_path.exists(), "entity page should be in entities/ after retry"
    assert not review_path.exists(), (
        "entity page must NOT be staged as review when prose retry succeeds"
    )

    content = entity_path.read_text(encoding="utf-8")
    assert "type: entity" in content
    assert "[[sources/retry-prose-source]]" in content

    # Source page is still written.
    assert (vault_root / "20. Wiki/20. Sources/retry-prose-source.md").exists()

    # Changes: entity + source, no review.
    kinds = {change.kind for change in result.changes}
    assert "entity" in kinds
    assert "source" in kinds
    assert "review" not in kinds


class _AllProseEntityClient:
    """Fake LLM client where both the first ``chat_stream`` AND the retry
    ``chat`` return prose (no JSON at all). STAB-002's fix requires that a
    brand-new page ends up in ``non_categories/`` as a pending review item
    when both attempts fail to produce a parseable page JSON."""

    provider = "ollama"

    def __init__(
        self,
        source_slug: str = "all-prose-source",
        slug: str = "openai",
    ):
        self.source_slug = source_slug
        self.slug = slug
        self.stream_calls = 0
        self.retry_calls = 0

    EXTRACTION_JSON = """{
  "title": "All Prose Source",
  "source_slug": "all-prose-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}"""

    PROSE = (
        "I'm sorry, I cannot generate a JSON object right now. "
        "OpenAI is an AI research company founded in 2015."
    )

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        if "이전 응답은 페이지 JSON" in prompt or "JSON 계약" in prompt:
            self.retry_calls += 1
            return self.PROSE  # still prose on retry
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            text = (
                "---\n"
                "title: All Prose Source\n"
                "type: source\n"
                "tags: [ai]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# All Prose Source\n\n"
                "Source summary.\n"
            )
        else:
            self.stream_calls += 1
            text = self.PROSE
        if False:
            yield ""
        return text


def test_stab002_both_attempts_prose_routes_to_review(tmp_path, monkeypatch):
    """STAB-002 fallback: both ``chat_stream`` and the retry ``chat`` return
    prose that fails to parse as page JSON. For a brand-new page (no merge
    target), STAB-002 routes the entity to ``non_categories/`` with
    ``status: pending_review`` instead of letting it silently commit."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths, _ = _setup_internal_wiki(tmp_path)
    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/all-prose.md",
        "# All Prose\n\nOpenAI details.",
    )

    client = _AllProseEntityClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # Both attempts happened.
    assert client.stream_calls == 1
    assert client.retry_calls == 1

    # Ingest finished without a hard error: the entity was diverted to review.
    assert result.ok, f"ingest failed: {result.error}"
    kinds = {change.kind for change in result.changes}
    assert "review" in kinds, f"expected a review change, got {kinds}"

    vault_root = tmp_path / "vault"
    # Entity directory is empty.
    assert not (vault_root / "20. Wiki/22. Entities/openai.md").exists()
    # Review file lives in non_categories/ with pending_review status.
    review_path = vault_root / "00. Inbox/_Review/openai.md"
    assert review_path.exists(), "entity should be staged as a review item"

    content = review_path.read_text(encoding="utf-8")
    assert "pageKind: review" in content
    assert "type: review" in content
    assert "status: pending_review" in content
    # Reason should reference the parse failure.
    assert "Reason" in content
    assert any(
        marker in content
        for marker in (
            "parse",
            "JSON",
            "Invalid",
            "structured",
        )
    ), f"review reason should reference parse failure: {content!r}"

    # Source page is still written.
    assert (vault_root / "20. Wiki/20. Sources/all-prose-source.md").exists()


class _StreamCallbackRaisesClient:
    """Fake LLM client whose ``chat_stream`` yields a normal page JSON chunk
    followed by a second chunk that triggers ``callbacks.on_stream_chunk``.
    The fake callback (see below) raises ``ValueError`` on the entity stream
    chunks, simulating a CLI bailout (e.g. Rich/CLI closed the stream)."""

    provider = "ollama"

    def __init__(
        self,
        source_slug: str = "callback-raise-source",
        slug: str = "openai",
    ):
        self.source_slug = source_slug
        self.slug = slug
        self.entity_stream_calls = 0

    EXTRACTION_JSON = """{
  "title": "Callback Raise Source",
  "source_slug": "callback-raise-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}"""

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            # Source page is fine — keep it stable so the failure is localised
            # to the entity stream.
            text = (
                "---\n"
                "title: Callback Raise Source\n"
                "type: source\n"
                "tags: [ai]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# Callback Raise Source\n\n"
                "Source summary.\n"
            )
            yield text
        else:
            self.entity_stream_calls += 1
            # Chunk the entity page JSON so the callback can fire and raise
            # between chunks. The first chunk is well-formed; the second
            # chunk is delivered and triggers the ValueError via the callback.
            text = json.dumps(
                {
                    "slug": self.slug,
                    "type": "entity",
                    "body_markdown": (
                        f"# OpenAI\n\n"
                        f"OpenAI is an AI research company.\n\n"
                        f"## 출처\n\n"
                        f"[[sources/{self.source_slug}]]\n"
                    ),
                    "links_used": [f"sources/{self.source_slug}"],
                    "sources": [f"sources/{self.source_slug}.md"],
                }
            )
            mid = max(1, len(text) // 2)
            yield text[:mid]
            yield text[mid:]


class _StreamChunkRaisesCallbacks(IngestCallbacks):
    """``IngestCallbacks`` subclass that raises ``ValueError`` on stream chunks
    belonging to the entity page draft. Source-page chunks (delivered first)
    are passed through cleanly."""

    def __init__(self):
        super().__init__()
        self.entity_chunks_seen = 0

    def on_stream_chunk(self, chunk: str) -> None:
        # The source page is the first stream call (single chunk). After it
        # is consumed the entity stream starts. We treat the second and later
        # chunks as entity chunks and raise on the second one.
        self.entity_chunks_seen += 1
        if self.entity_chunks_seen >= 2:
            raise ValueError("simulated CLI bailout on stream chunk")


def test_stab003_stream_callback_exception_is_surfaced(tmp_path, monkeypatch):
    """STAB-003: a ``ValueError`` raised from ``callbacks.on_stream_chunk``
    during the entity page draft must surface as an ``IngestResult.error``
    instead of being silently absorbed as a "JSON parse failure"."""
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths, _ = _setup_internal_wiki(tmp_path)
    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/callback-raise.md",
        "# Callback Raise\n\nOpenAI details.",
    )

    client = _StreamCallbackRaisesClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        _StreamChunkRaisesCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # Callback exception is surfaced as an error result, NOT as a silent success.
    assert not result.ok, (
        "stream callback ValueError must be surfaced as an IngestResult.error, "
        "not silently swallowed"
    )
    assert result.error is not None
    assert "Failed drafting" in result.error, (
        f"error should reference failed drafting, got: {result.error!r}"
    )
    assert "simulated CLI bailout" in result.error, (
        f"the original callback exception message must be preserved, got: "
        f"{result.error!r}"
    )

    # The entity draft was attempted at least once.
    assert client.entity_stream_calls == 1

    # Transactional discipline: no entity page committed.
    vault_root = tmp_path / "vault"
    assert not (vault_root / "20. Wiki/22. Entities/openai.md").exists(), (
        "callback exception must not let the entity page commit"
    )

    # DB source status flips to "error".
    with db.connect(paths.state_db) as conn:
        row = conn.execute(
            "SELECT status FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
    assert row is not None
    assert row["status"] == "error", (
        f"source status should be 'error' after callback exception, "
        f"got {row['status']!r}"
    )
