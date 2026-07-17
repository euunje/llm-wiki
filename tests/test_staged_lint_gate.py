"""Regression tests for STAB-001 staged lint gate.

The Stage 1 transactional discipline ("pages are staged and only committed to
``wiki/`` on success") requires the lint gate to run BEFORE the staged files are
copied into the wiki. These tests verify that:

* A page that survives ``_validate_generated_page`` but is broken at the wiki
  level (e.g. a body wikilink whose target does not exist) causes the entire
  ingest to abort with an error.
* When the lint gate rejects the staged set, the wiki state on disk must NOT
  receive the new page (no commit), and no review-fallback file is written
  either. The DB source status flips to ``error``.

The tests deliberately use the default ``.wiki/config.yml`` location instead of
``LLM_WIKI_CONFIG``. This avoids a config-overwrite side effect inside
``_build_staged_lint_paths`` (where the lint staging config otherwise replaces
the runtime config) that is independent of the STAB-001 fix being verified here.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from llm_wiki import config as cfg
from llm_wiki import db, lint
from llm_wiki.ingest_llm import (
    IngestCallbacks,
    ingest_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_internal_config(tmp_path: Path, vault_root: Path) -> Path:
    """Write the runtime config to ``<vault_root>/.wiki/config.yml``.

    Using the default internal location (no ``LLM_WIKI_CONFIG`` env override)
    keeps the lint staging config from clobbering the runtime config during
    ``_build_staged_lint_paths``. ``files.state_db`` lives at the default
    ``<root>/.wiki/state.sqlite`` so it survives that overwrite.
    """
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
    return config_path


def _register_markdown_source(paths, relpath: str, text: str) -> int:
    """Create the raw source file and register it as ``pending`` in the state DB."""
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
            (
                relpath,
                f"hash-{relpath}",
                "markdown",
                source_path.stat().st_size,
                "2026-07-15T00:00:00Z",
                "pending",
            ),
        )
        return conn.execute("SELECT id FROM sources ORDER BY id DESC LIMIT 1").fetchone()[0]


def _seed_existing_entity(paths, slug: str, title: str) -> Path:
    """Write a syntactically valid entity page directly under ``paths.entities``.

    Returns the absolute path of the seeded page so callers can assert it
    remains untouched after the failing ingest.
    """
    page_path = paths.entities / f"{slug}.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(
        f"""---
title: {title}
type: entity
created: 2026-07-15
updated: 2026-07-15
sources:
- sources/seeded-source.md
---

# {title}

This page already exists in the wiki and must remain after the ingest aborts.
""",
        encoding="utf-8",
    )
    return page_path


# ---------------------------------------------------------------------------
# Fake LLM client
# ---------------------------------------------------------------------------


class _LintGateFakeClient:
    """Returns an entity page that validates cleanly, plus a source page whose
    body contains a wikilink to a page that does NOT exist anywhere in the wiki.

    The entity page passes ``_validate_generated_page`` (all wikilinks are in
    ``allowed_links``), so it would normally be staged to ``entities/``. The
    source page, on the other hand, is not subject to ``_validate_generated_page``
    and is staged as-is. Once both pages hit the staged lint gate, the broken
    wikilink in the source page is detected as an unfixable ``broken_wikilink``
    ERROR by ``check_broken_wikilinks``, and the staged set is rejected.
    """

    provider = "ollama"

    EXTRACTION_JSON = """{
  "title": "Lint Gate Source",
  "source_slug": "lint-gate-source",
  "summary": "Source summary.",
  "key_takeaways": ["Takeaway"],
  "candidates": [
    {
      "name": "New Entity",
      "slug": "new-entity",
      "pageKind": "entity",
      "description": "A new entity being ingested.",
      "confidence": "high"
    }
  ],
  "entities": [],
  "concepts": [],
  "tags": ["test"]
}"""

    def __init__(self, broken_target: str = "entities/non-existent-target"):
        self._broken_target = broken_target

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "key_takeaways" in prompt and "candidates" in prompt:
            return self.EXTRACTION_JSON
        # Page-retry path is not exercised by this test.
        return "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "source summary page" in prompt:
            # Source page — its body contains a wikilink whose target does not
            # exist in the wiki. Lint flags this as an unfixable broken_wikilink.
            text = (
                "---\n"
                "title: Lint Gate Source\n"
                "type: source\n"
                "tags: [test]\n"
                "created: 2026-07-15\n"
                "updated: 2026-07-15\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                f"# Lint Gate Source\n\n"
                f"See [[{self._broken_target}]] for context.\n\n"
                "This source intentionally references a page that does not exist.\n"
            )
        else:
            # Entity page — fully valid GeneratedPage JSON. The body only
            # references the source page, which is in allowed_links.
            text = json.dumps(
                {
                    "slug": "new-entity",
                    "type": "entity",
                    "body_markdown": (
                        "# New Entity\n\n"
                        "A new entity that should not be committed because the\n"
                        "staged lint gate fails on the sibling source page.\n\n"
                        "## 출처\n\n"
                        "[[sources/lint-gate-source]]\n"
                    ),
                    "links_used": ["sources/lint-gate-source"],
                    "sources": ["sources/lint-gate-source.md"],
                }
            )
        if False:
            yield ""
        return text


# ---------------------------------------------------------------------------
# Test: STAB-001 staged lint gate
# ---------------------------------------------------------------------------


def test_staged_lint_gate_rejects_broken_wikilink(tmp_path, monkeypatch):
    """When the staged lint gate detects a broken wikilink that validation
    cannot prevent, the ingest must abort before any commit happens.

    The test pre-seeds one valid entity page, runs ingest_source with a fake
    LLM that produces a valid entity page plus a source page containing a
    wikilink to a non-existent target, and verifies that:

    * ``result.ok`` is ``False`` and ``result.error`` references the lint failure.
    * The new entity page is NOT committed to ``entities/``.
    * No review fallback file is written to ``non_categories/``.
    * The source page is NOT committed to ``sources/``.
    * The seeded existing entity page is untouched.
    * DB source status flips to ``"error"``.
    * No ``index.md`` / ``log.md`` entry is appended for the failed ingest
      (best-effort assertion).
    """
    # Defensive: make sure no stale LLM_WIKI_CONFIG leaks across tests.
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)

    vault_root = tmp_path / "vault"
    _write_internal_config(tmp_path, vault_root)
    paths = cfg.WikiPaths(vault_root)

    # Pre-seed one valid entity page so the wiki is non-empty.
    seeded_entity = _seed_existing_entity(paths, "existing-entity", "Existing Entity")

    # Capture log.md and index.md state before ingest so we can verify nothing
    # was appended after the lint failure.
    log_path = paths.log
    index_path = paths.index
    log_existed_before = log_path.exists()
    index_existed_before = index_path.exists()
    log_text_before = log_path.read_text(encoding="utf-8") if log_existed_before else ""
    index_text_before = index_path.read_text(encoding="utf-8") if index_existed_before else ""

    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/lint-gate-source.md",
        "# Lint Gate Source\n\nA new entity is being created from this source.",
    )

    client = _LintGateFakeClient()
    result = ingest_source(
        paths,
        source_id,
        client,
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    # 1. Ingest result reflects the lint failure.
    assert not result.ok, f"ingest should have failed, got: {result.error}"
    assert result.error is not None
    assert "lint" in result.error.lower(), (
        f"error message should reference lint failure, got: {result.error!r}"
    )
    assert "sources/lint-gate-source.md" in result.error
    assert "broken_wikilink" in result.error
    assert "non-existent-target" in result.error
    assert "not fixable" in result.error

    # 2. New entity is NOT committed to entities/.
    entity_path = vault_root / "20. Wiki/22. Entities/new-entity.md"
    assert not entity_path.exists(), (
        "staged lint gate failed but new entity page was still committed"
    )

    # 3. Source page is NOT committed to sources/.
    source_path = vault_root / "20. Wiki/20. Sources/lint-gate-source.md"
    assert not source_path.exists(), (
        "staged lint gate failed but source page was still committed"
    )

    # 4. No review fallback file is written either.
    review_path = vault_root / "00. Inbox/_Review/new-entity.md"
    assert not review_path.exists(), (
        "no review fallback should be written when lint gate fails"
    )
    review_dir = vault_root / "00. Inbox" / "_Review"
    if review_dir.exists():
        assert not list(review_dir.glob("*.md")), (
            f"non_categories must be empty on lint-gate failure, "
            f"found: {list(review_dir.glob('*.md'))}"
        )

    # 5. The seeded existing entity is untouched.
    assert seeded_entity.exists(), "seeded existing entity must remain after abort"
    seeded_text = seeded_entity.read_text(encoding="utf-8")
    assert "This page already exists" in seeded_text

    # 6. DB source status flips to "error".
    with db.connect(paths.state_db) as conn:
        row = conn.execute(
            "SELECT status FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
    assert row is not None
    assert row["status"] == "error", (
        f"source status should be 'error' after lint-gate failure, got {row['status']!r}"
    )

    # 7. Best-effort: no index.md / log.md entry appended for this failed ingest.
    if log_path.exists():
        assert log_path.read_text(encoding="utf-8") == log_text_before, (
            "log.md should not have been appended after a lint-gate failure"
        )
    if index_path.exists():
        assert index_path.read_text(encoding="utf-8") == index_text_before, (
            "index.md should not have been regenerated after a lint-gate failure"
        )

    # 8. Lint itself confirms the broken_wikilink diagnosis (sanity check).
    # When we run the staged lint directly on the source-page body we see the
    # exact failure mode that the staged gate detected.
    broken_target = "entities/non-existent-target"
    fake_source_body = (
        "See [[" + broken_target + "]] for context.\n"
    )
    issues = lint.check_broken_wikilinks(
        type("Inv", (), {
            "all_slugs": {"entities/existing-entity", "sources/lint-gate-source"},
            "outgoing_links": {"sources/lint-gate-source": {broken_target}},
        })()
    )
    assert issues, "expected lint to flag the broken wikilink in the source page"
    assert any("non-existent-target" in i.message for i in issues), (
        f"lint should flag the missing target, got: {[i.message for i in issues]}"
    )


def test_staged_lint_gate_preserves_existing_source_page_on_abort(tmp_path, monkeypatch):
    """If a generated update fails staged lint, the existing source page remains unchanged.

    The ingest pipeline stages generated files first and only copies them into the
    real wiki after the staged lint gate passes.  This test verifies the common
    user-visible case where a source summary page already exists: a later retry
    that fails lint must not partially overwrite that existing page.
    """
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)

    vault_root = tmp_path / "vault"
    _write_internal_config(tmp_path, vault_root)
    paths = cfg.WikiPaths(vault_root)

    existing_source = paths.sources / "lint-gate-source.md"
    existing_source.parent.mkdir(parents=True, exist_ok=True)
    existing_text = (
        "---\n"
        "title: Existing Lint Gate Source\n"
        "type: source\n"
        "created: 2026-07-14\n"
        "updated: 2026-07-14\n"
        "---\n\n"
        "# Existing Lint Gate Source\n\n"
        "This existing source page must survive a failed staged update.\n"
    )
    existing_source.write_text(existing_text, encoding="utf-8")

    source_id = _register_markdown_source(
        paths,
        "10. Raw Sources/lint-gate-source.md",
        "# Lint Gate Source\n\nA retry tries to update the source page.",
    )

    result = ingest_source(
        paths,
        source_id,
        _LintGateFakeClient(),
        IngestCallbacks(),
        mode="batch",
        thinking_for_extraction=False,
    )

    assert not result.ok
    assert "Lint errors remain on staged pages after auto-fix" in (result.error or "")
    assert existing_source.read_text(encoding="utf-8") == existing_text
    assert not (paths.entities / "new-entity.md").exists()
