"""Regression tests for Phase 2 extraction/routing schema alignment.

Verifies:
- _parse_extraction accepts new candidates[] JSON with entity/concept/review kinds
- Legacy entities[]/concepts[] JSON still parses and normalizes
- _write_review_candidate routes review items to non_categories with correct metadata
- Configured page dirs are respected (paths.page_dir integration)
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import yaml

from llm_wiki import config as cfg
from llm_wiki import db, lint, relinker
from llm_wiki.webapp.main import create_app
from llm_wiki.ingest_llm import (
    ExtractedCandidate,
    IngestCallbacks,
    _parse_extraction,
    _write_review_candidate,
    ingest_source,
)


# ---------------------------------------------------------------------------
# Test: candidates[] JSON with entity, concept, and review kinds parses correctly
# ---------------------------------------------------------------------------

def test_parse_extraction_candidates_entity_concept_review():
    raw = """{
  "title": "Test Doc",
  "source_slug": "test-doc",
  "summary": "A test document",
  "key_takeaways": ["Point 1", "Point 2"],
  "candidates": [
    {
      "name": "Andrej Karpathy",
      "slug": "karpathy",
      "pageKind": "entity",
      "description": "AI researcher and educator.",
      "confidence": "high",
      "suggestedExternalOwner": null,
      "reason": null
    },
    {
      "name": "Retrieval-Augmented Generation",
      "slug": "rag",
      "pageKind": "concept",
      "description": "A method for augmenting LLMs with external knowledge.",
      "confidence": "high",
      "suggestedExternalOwner": null,
      "reason": null
    },
    {
      "name": "DevOps Runbook",
      "slug": "devops-runbook",
      "pageKind": "review",
      "description": "Runbook for deploying the service.",
      "confidence": "low",
      "suggestedExternalOwner": "8000-web-config",
      "reason": "Operational guide — not a wiki entity or concept."
    },
    {
      "name": "Architecture Map",
      "slug": "architecture-map",
      "pageKind": "review",
      "description": "Hub page showing service relationships.",
      "confidence": "medium",
      "suggestedExternalOwner": "mcp-map",
      "reason": "Map/MOC — not a wiki entity or concept."
    }
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai", "llm"]
}"""

    ext = _parse_extraction(raw)

    assert ext.title == "Test Doc"
    assert ext.source_slug == "test-doc"

    # candidates[] preserved
    assert len(ext.candidates) == 4
    entity_cands = [c for c in ext.candidates if c.pageKind == "entity"]
    concept_cands = [c for c in ext.candidates if c.pageKind == "concept"]
    review_cands = [c for c in ext.candidates if c.pageKind == "review"]

    assert len(entity_cands) == 1
    assert entity_cands[0].name == "Andrej Karpathy"
    assert entity_cands[0].slug == "karpathy"
    assert entity_cands[0].confidence == "high"

    assert len(concept_cands) == 1
    assert concept_cands[0].name == "Retrieval-Augmented Generation"
    assert concept_cands[0].slug == "rag"

    assert len(review_cands) == 2
    config_review = next(c for c in review_cands if c.suggestedExternalOwner == "8000-web-config")
    assert config_review.slug == "devops-runbook"
    assert config_review.reason == "Operational guide — not a wiki entity or concept."

    map_review = next(c for c in review_cands if c.suggestedExternalOwner == "mcp-map")
    assert map_review.slug == "architecture-map"

    # Entity/concept candidates are projected back into legacy arrays so
    # existing CLI/jobs callbacks and draft loops still run on new-schema JSON.
    assert len(ext.entities) == 1
    assert ext.entities[0].name == "Andrej Karpathy"
    assert ext.entities[0].slug == "karpathy"
    assert len(ext.concepts) == 1
    assert ext.concepts[0].name == "Retrieval-Augmented Generation"
    assert ext.concepts[0].slug == "rag"


# ---------------------------------------------------------------------------
# Test: legacy entities[]/concepts[] JSON still normalises to candidates
# ---------------------------------------------------------------------------

def test_parse_extraction_legacy_entities_concepts_normalizes():
    raw = """{
  "title": "Legacy Doc",
  "source_slug": "legacy-doc",
  "summary": "Old-format extraction",
  "key_takeaways": ["Takeaway"],
  "entities": [
    {"name": "OpenAI", "slug": "openai", "type": "organization", "description": "AI company."}
  ],
  "concepts": [
    {"name": "Chain of Thought", "slug": "chain-of-thought", "type": "concept", "description": "Reasoning technique."}
  ],
  "tags": ["ai"]
}"""

    ext = _parse_extraction(raw)

    # Legacy fields preserved
    assert len(ext.entities) == 1
    assert ext.entities[0].name == "OpenAI"
    assert len(ext.concepts) == 1
    assert ext.concepts[0].name == "Chain of Thought"

    # Normalized into candidates
    assert len(ext.candidates) == 2
    entity_cand = next(c for c in ext.candidates if c.pageKind == "entity")
    assert entity_cand.name == "OpenAI"
    assert entity_cand.slug == "openai"

    concept_cand = next(c for c in ext.candidates if c.pageKind == "concept")
    assert concept_cand.name == "Chain of Thought"


# ---------------------------------------------------------------------------
# Test: candidates[] takes precedence over empty legacy arrays
# ---------------------------------------------------------------------------

def test_parse_extraction_candidates_takes_precedence():
    raw = """{
  "title": "Mixed",
  "source_slug": "mixed",
  "summary": "Mixed format",
  "key_takeaways": [],
  "candidates": [
    {"name": "Alpha", "slug": "alpha", "pageKind": "entity", "description": "First.", "confidence": "high"}
  ],
  "entities": [
    {"name": "Should Not Appear", "slug": "should-not-appear", "type": "organization", "description": "X."}
  ],
  "concepts": [],
  "tags": []
}"""

    ext = _parse_extraction(raw)

    # candidates[] wins
    assert len(ext.candidates) == 1
    assert ext.candidates[0].name == "Alpha"
    # candidates[] wins for normalized ingest-facing legacy projections too.
    assert len(ext.entities) == 1
    assert ext.entities[0].name == "Alpha"


# ---------------------------------------------------------------------------
# Test: _write_review_candidate writes correct file with correct frontmatter
# ---------------------------------------------------------------------------

def test_write_review_candidate_frontmatter_and_path(tmp_path, monkeypatch):
    """Ja-mapped paths via LLM_WIKI_CONFIG monkeypatch."""
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "runtime"

    wiki = vault_root / "20. Wiki"
    sources = wiki / "20. Sources"
    entities = wiki / "22. Entities"
    concepts = wiki / "21. Concepts"
    synthesis = vault_root / "30. Queries"
    non_cat = vault_root / "00. Inbox" / "_Review"

    for d in (sources, entities, concepts, synthesis, non_cat, runtime):
        d.mkdir(parents=True, exist_ok=True)

    runtime_config = runtime / "config.yml"
    runtime_config.write_text(
        yaml.safe_dump({
            "paths": {
                "root": str(vault_root),
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
        }),
        encoding="utf-8",
    )

    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)

    # Verify paths resolved correctly before asserting file writes
    assert paths.entities == (vault_root / "20. Wiki" / "22. Entities").resolve(), \
        f"entities = {paths.entities}"
    assert paths.non_categories == (vault_root / "00. Inbox" / "_Review").resolve(), \
        f"non_categories = {paths.non_categories}"

    cand = ExtractedCandidate(
        name="My Runbook",
        slug="my-runbook",
        pageKind="review",
        description="Steps to restart the service.",
        confidence="low",
        suggestedExternalOwner="8000-web-config",
        reason="Operational guide.",
    )

    change = _write_review_candidate(
        paths=paths,
        candidate=cand,
        source_slug="test-doc",
        extraction_tags=["ops", "runbook"],
        today="2026-07-13",
    )

    # Returns correct change object
    assert change.slug == "my-runbook"
    assert change.kind == "review"
    assert change.operation == "created"
    assert change.path == "non_categories/my-runbook.md"

    # File written to the configured non_categories path (Ja layout)
    expected = vault_root / "00. Inbox" / "_Review" / "my-runbook.md"
    assert expected.exists(), f"Expected {expected}"

    content = expected.read_text(encoding="utf-8")
    assert "title: My Runbook" in content
    assert "type: review" in content
    assert "pageKind: review" in content
    assert "status: pending_review" in content
    assert "confidence: low" in content
    assert "suggestedExternalOwner: 8000-web-config" in content
    assert "sources/test-doc.md" in content
    assert "Steps to restart the service." in content
    assert "Operational guide." in content


# ---------------------------------------------------------------------------
# Test: review candidate with no suggestedExternalOwner writes cleanly
# ---------------------------------------------------------------------------

def test_write_review_candidate_no_owner(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "runtime"

    non_cat = vault_root / "00. Inbox" / "_Review"
    (runtime / "config.yml").parent.mkdir(parents=True, exist_ok=True)
    (runtime / "config.yml").write_text(
        yaml.safe_dump({
            "paths": {
                "root": str(vault_root),
                "internal_dir": str(runtime),
                "wiki_dir": "20. Wiki",
                "page_dirs": {
                    "non_categories": "00. Inbox/_Review",
                },
            }
        }),
        encoding="utf-8",
    )

    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime / "config.yml"))
    paths = cfg.WikiPaths(vault_root)

    cand = ExtractedCandidate(
        name="Ambiguous Topic",
        slug="ambiguous-topic",
        pageKind="review",
        description="Unclear if entity or concept.",
        confidence="medium",
        suggestedExternalOwner=None,
        reason=None,
    )

    change = _write_review_candidate(
        paths=paths,
        candidate=cand,
        source_slug="doc-xyz",
        extraction_tags=["misc"],
        today="2026-07-13",
    )

    assert change.path == "non_categories/ambiguous-topic.md"

    content = (vault_root / "00. Inbox" / "_Review" / "ambiguous-topic.md").read_text(encoding="utf-8")
    # When suggestedExternalOwner is None it is absent from frontmatter (not written as null/empty)
    assert "suggestedExternalOwner" not in content
    assert "Ambiguous Topic" in content
    assert "Unclear if entity or concept." in content


# ---------------------------------------------------------------------------
# Test: page_dir resolution uses configured Ja layout (not hardcoded wiki/)
# ---------------------------------------------------------------------------

def test_page_dir_uses_configured_path(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "runtime"

    wiki = vault_root / "20. Wiki"
    (wiki / "20. Sources").mkdir(parents=True)
    (wiki / "22. Entities").mkdir(parents=True)
    (wiki / "21. Concepts").mkdir(parents=True)
    (vault_root / "30. Queries").mkdir(parents=True)
    (runtime).mkdir(parents=True)

    config = {
        "paths": {
            "root": str(vault_root),
            "internal_dir": str(runtime),
            "wiki_dir": "20. Wiki",
            "page_dirs": {
                "sources": "20. Wiki/20. Sources",
                "entities": "20. Wiki/22. Entities",
                "concepts": "20. Wiki/21. Concepts",
                "synthesis": "30. Queries",
                "non_categories": "00. Inbox/_Review",
            },
        }
    }
    (runtime / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime / "config.yml"))

    paths = cfg.WikiPaths(vault_root)

    assert paths.sources == (vault_root / "20. Wiki" / "20. Sources").resolve()
    assert paths.entities == (vault_root / "20. Wiki" / "22. Entities").resolve()
    assert paths.concepts == (vault_root / "20. Wiki" / "21. Concepts").resolve()
    assert paths.synthesis == (vault_root / "30. Queries").resolve()
    assert paths.non_categories == (vault_root / "00. Inbox" / "_Review").resolve()


# ---------------------------------------------------------------------------
# Test: review candidate writes to configured non_categories (not hardcoded)
# ---------------------------------------------------------------------------

def test_review_candidate_uses_configured_non_categories(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "runtime"

    non_cat = vault_root / "00. Inbox" / "_Review"
    non_cat.mkdir(parents=True)
    (runtime).mkdir(parents=True)
    (runtime / "config.yml").write_text(
        yaml.safe_dump({
            "paths": {
                "root": str(vault_root),
                "internal_dir": str(runtime),
                "wiki_dir": "20. Wiki",
                "page_dirs": {
                    "non_categories": "00. Inbox/_Review",
                },
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime / "config.yml"))

    paths = cfg.WikiPaths(vault_root)

    cand = ExtractedCandidate(
        name="Low Confidence Item",
        slug="low-confidence-item",
        pageKind="review",
        description="Not sure what this is.",
        confidence="low",
        suggestedExternalOwner=None,
        reason=None,
    )

    change = _write_review_candidate(
        paths=paths,
        candidate=cand,
        source_slug="s1",
        extraction_tags=["test"],
        today="2026-07-13",
    )

    # Must go to the configured Ja non_categories path
    expected = vault_root / "00. Inbox" / "_Review" / "low-confidence-item.md"
    assert expected.exists()
    # Confirm it did NOT go to wiki/non_categories
    wrong = vault_root / "20. Wiki" / "non_categories" / "low-confidence-item.md"
    assert not wrong.exists(), "Review item should not be written to wiki/non_categories"


# ---------------------------------------------------------------------------
# Test: ExtractedCandidate model validation
# ---------------------------------------------------------------------------

def test_extracted_candidate_defaults():
    cand = ExtractedCandidate(name="Test", slug="test")
    assert cand.pageKind == "entity"
    assert cand.description == ""
    assert cand.confidence is None
    assert cand.suggestedExternalOwner is None
    assert cand.reason is None


def test_extraction_model_has_candidates_field():
    raw = '{"title": "T", "source_slug": "t", "summary": "S", "candidates": [], "entities": [], "concepts": [], "tags": []}'
    ext = _parse_extraction(raw)
    assert hasattr(ext, "candidates")
    assert ext.candidates == []


class _FakeCandidateClient:
    def chat(self, messages, **kwargs):
        return """{
  "title": "Candidate Only Source",
  "source_slug": "candidate-only-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"},
    {"name": "Retrieval-Augmented Generation", "slug": "rag", "pageKind": "concept", "description": "LLM retrieval pattern.", "confidence": "high"},
    {"name": "Deploy Runbook", "slug": "deploy-runbook", "pageKind": "review", "description": "Operational deployment guide.", "confidence": "low", "suggestedExternalOwner": "8000-web-config", "reason": "Guide-like operational content."}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ai", "ops"]
}"""

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "entity page" in prompt:
            text = """---
title: OpenAI
type: entity
tags: [ai]
created: 2026-07-13
updated: 2026-07-13
sources: []
confidence: high
---

# OpenAI

OpenAI is an AI company.
"""
        elif "concept page" in prompt:
            text = """---
title: Retrieval-Augmented Generation
type: concept
tags: [ai]
created: 2026-07-13
updated: 2026-07-13
sources: []
confidence: high
---

# Retrieval-Augmented Generation

RAG combines retrieval with generation.
"""
        else:
            text = """---
title: Candidate Only Source
type: source
tags: [ai, ops]
created: 2026-07-13
updated: 2026-07-13
file_path: /api/raw-download/1
file_type: markdown
---

# Candidate Only Source

Source summary.
"""
        if False:
            yield ""
        return text


def test_ingest_source_candidate_only_schema_routes_all_outputs(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "runtime"
    raw_dir = vault_root / "10. Raw Sources"
    raw_dir.mkdir(parents=True)
    source_file = raw_dir / "candidate.md"
    source_file.write_text("# Candidate Only Source\n\nOpenAI uses RAG. Deploy runbook details.", encoding="utf-8")

    runtime.mkdir(parents=True)
    runtime_config = runtime / "config.yml"
    runtime_config.write_text(
        yaml.safe_dump(
            {
                "paths": {
                    "root": str(vault_root),
                    "raw_dir": "10. Raw Sources",
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
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            """
            INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "10. Raw Sources/candidate.md",
                "hash-candidate",
                "markdown",
                source_file.stat().st_size,
                "2026-07-13T00:00:00Z",
                "pending",
            ),
        )
        source_id = conn.execute("SELECT id FROM sources").fetchone()[0]

    result = ingest_source(
        paths,
        source_id,
        _FakeCandidateClient(),
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    assert result.ok
    assert (vault_root / "20. Wiki/22. Entities/openai.md").exists()
    assert (vault_root / "20. Wiki/21. Concepts/rag.md").exists()
    assert (vault_root / "20. Wiki/20. Sources/candidate-only-source.md").exists()
    review_path = vault_root / "00. Inbox/_Review/deploy-runbook.md"
    assert review_path.exists()
    review_text = review_path.read_text(encoding="utf-8")
    assert "pageKind: review" in review_text
    assert "suggestedExternalOwner: 8000-web-config" in review_text
    assert not (vault_root / "20. Wiki/23. Guides/deploy-runbook.md").exists()
    assert not (vault_root / "20. Wiki/24. Maps/deploy-runbook.md").exists()
    assert {change.kind for change in result.changes} == {"entity", "concept", "source", "review"}


class _RejectingCallbacks(IngestCallbacks):
    def ask_confirm(self, extraction):
        return False


class _FakeReviewOnlyClient:
    def chat(self, messages, **kwargs):
        return """{
  "title": "Review Only Source",
  "source_slug": "review-only-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {"name": "Deploy Runbook", "slug": "deploy-runbook", "pageKind": "review", "description": "Operational guide.", "confidence": "low", "suggestedExternalOwner": "8000-web-config"}
  ],
  "entities": [],
  "concepts": [],
  "tags": ["ops"]
}"""

    def chat_stream(self, messages, **kwargs):
        raise AssertionError("skip path should not draft pages")


def _write_ja_runtime_config(vault_root, runtime, raw_dir="10. Raw Sources"):
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
            (relpath, f"hash-{relpath}", "markdown", source_path.stat().st_size, "2026-07-13T00:00:00Z", "pending"),
        )
        return conn.execute("SELECT id FROM sources ORDER BY id DESC LIMIT 1").fetchone()[0]


def test_review_candidates_not_written_when_ingest_skipped(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_markdown_source(paths, "10. Raw Sources/review.md", "# Review\n\nDeploy runbook.")

    result = ingest_source(
        paths,
        source_id,
        _FakeReviewOnlyClient(),
        _RejectingCallbacks(),
        mode="interactive",
        thinking_for_extraction=False,
    )

    assert result.skipped
    assert not (vault_root / "00. Inbox/_Review/deploy-runbook.md").exists()


class _FakeLowConfidenceClient:
    def __init__(self, kind: str):
        self.kind = kind

    def chat(self, messages, **kwargs):
        if self.kind == "entity":
            candidates = '{"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "AI company.", "confidence": "high"}'
        else:
            candidates = '{"name": "Retrieval-Augmented Generation", "slug": "rag", "pageKind": "concept", "description": "LLM retrieval pattern.", "confidence": "high"}'
        return f"""{{
  "title": "Low Confidence Source",
  "source_slug": "low-confidence-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [{candidates}],
  "entities": [],
  "concepts": [],
  "tags": ["ai"]
}}"""

    def chat_stream(self, messages, **kwargs):
        if self.kind == "entity":
            text = """---
title: OpenAI
type: entity
tags: [ai]
created: 2026-07-13
updated: 2026-07-13
sources: []
confidence: 0.5
---

# OpenAI

Low confidence entity draft.
"""
        elif self.kind == "concept":
            text = """---
title: Retrieval-Augmented Generation
type: concept
tags: [ai]
created: 2026-07-13
updated: 2026-07-13
sources: []
confidence: low
---

# Retrieval-Augmented Generation

Low confidence concept draft.
"""
        else:
            text = """---
title: Low Confidence Source
type: source
tags: [ai]
created: 2026-07-13
updated: 2026-07-13
file_path: /api/raw-download/1
file_type: markdown
---

# Low Confidence Source

Source summary.
"""
        if False:
            yield ""
        return text


def test_low_confidence_entity_routes_to_configured_non_categories(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_markdown_source(paths, "10. Raw Sources/entity.md", "# Entity\n\nOpenAI.")

    result = ingest_source(paths, source_id, _FakeLowConfidenceClient("entity"), IngestCallbacks(), mode="batch", thinking_for_extraction=False)

    assert result.ok
    assert (vault_root / "00. Inbox/_Review/openai.md").exists()
    assert not (vault_root / "20. Wiki/22. Entities/openai.md").exists()
    content = (vault_root / "00. Inbox/_Review/openai.md").read_text(encoding="utf-8")
    assert "status: pending_review" in content
    assert "confidence: 0.5" in content


def test_low_confidence_concept_routes_to_configured_non_categories(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_markdown_source(paths, "10. Raw Sources/concept.md", "# Concept\n\nRAG.")

    result = ingest_source(paths, source_id, _FakeLowConfidenceClient("concept"), IngestCallbacks(), mode="batch", thinking_for_extraction=False)

    assert result.ok
    assert (vault_root / "00. Inbox/_Review/rag.md").exists()
    assert not (vault_root / "20. Wiki/21. Concepts/rag.md").exists()
    content = (vault_root / "00. Inbox/_Review/rag.md").read_text(encoding="utf-8")
    assert "status: pending_review" in content
    assert "confidence: low" in content


def test_relinker_promote_file_updates_ja_mapped_external_page_dirs(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    db.init_db(paths.state_db)

    paths.non_categories.mkdir(parents=True, exist_ok=True)
    paths.entities.mkdir(parents=True, exist_ok=True)
    paths.synthesis.mkdir(parents=True, exist_ok=True)
    review = paths.non_categories / "deploy-runbook.md"
    review.write_text("""---
title: Deploy Runbook
type: review
pageKind: review
status: pending_review
created: 2026-07-13
updated: 2026-07-13
---

# Deploy Runbook
""", encoding="utf-8")
    query = paths.synthesis / "ops-map.md"
    query.write_text("---\ntitle: Ops Map\ntype: synthesis\ncreated: 2026-07-13\n---\n\nSee [[non_categories/deploy-runbook]].\n", encoding="utf-8")
    with db.connect(paths.state_db) as conn:
        conn.execute(
            """
            INSERT INTO sources (id, relpath, content_hash, file_type, bytes, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "10. Raw Sources/source.md", "hash-source", "markdown", 1, "2026-07-13T00:00:00Z", "done"),
        )
        conn.execute(
            "INSERT INTO source_pages (source_id, wiki_path, operation, at) VALUES (?, ?, ?, ?)",
            (1, "non_categories/deploy-runbook.md", "created", "2026-07-13T00:00:00Z"),
        )

    assert relinker.promote_file(paths, "deploy-runbook", "entities")

    assert not review.exists()
    assert (vault_root / "20. Wiki/22. Entities/deploy-runbook.md").exists()
    assert "[[entities/deploy-runbook]]" in query.read_text(encoding="utf-8")
    with db.connect(paths.state_db) as conn:
        row = conn.execute("SELECT wiki_path FROM source_pages").fetchone()
    assert row["wiki_path"] == "entities/deploy-runbook.md"


def test_inbox_ui_shows_suggested_external_owner(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    paths.non_categories.mkdir(parents=True, exist_ok=True)
    db.init_db(paths.state_db)
    (paths.non_categories / "deploy-runbook.md").write_text("""---
title: Deploy Runbook
type: review
pageKind: review
status: pending_review
confidence: low
suggestedExternalOwner: 8000-web-config
processed_at: 2026-07-13T00:00:00Z
source_file: sources/source.md
created: 2026-07-13
updated: 2026-07-13
---

# Deploy Runbook
""", encoding="utf-8")

    response = TestClient(create_app(paths)).get("/inbox")

    assert response.status_code == 200
    assert "Suggested external owner" in response.text
    assert "8000-web-config" in response.text


def test_lint_does_not_flag_review_queue_items_as_orphans(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    runtime_config = _write_ja_runtime_config(vault_root, tmp_path / "runtime")
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(runtime_config))
    paths = cfg.WikiPaths(vault_root)
    paths.non_categories.mkdir(parents=True, exist_ok=True)
    (paths.non_categories / "ambiguous-topic.md").write_text("""---
title: Ambiguous Topic
type: review
pageKind: review
status: pending_review
created: 2026-07-13
updated: 2026-07-13
---

# Ambiguous Topic
""", encoding="utf-8")

    inv = lint._build_inventory(paths)
    issues = lint.check_orphan_pages(inv)

    assert not [issue for issue in issues if issue.page.endswith("ambiguous-topic.md")]
