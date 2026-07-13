"""Regression tests for fresh-start candidate/review guidance."""

from __future__ import annotations

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from llm_wiki import config as cfg
from llm_wiki.cli import app
from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def test_fresh_scaffold_creates_review_queue_and_candidate_rules(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)

    paths = scaffold(tmp_path)

    assert paths.non_categories.exists()
    assert paths.assets.exists()
    assert paths.state_db.exists()

    agents = paths.agents.read_text(encoding="utf-8")
    assert "pageKind: entity | concept | review" in agents
    assert "suggestedExternalOwner: 8000-web-config" in agents
    assert "suggestedExternalOwner: mcp-map" in agents
    assert "Never auto-file guide-like or map-like material" in agents
    assert "8–15" not in agents


def test_cli_ingest_help_uses_candidate_language():
    result = CliRunner().invoke(app, ["ingest", "--help"])

    assert result.exit_code == 0
    assert "extract candidates" in result.output
    assert "wiki/review pages" in result.output
    assert "extract entities/concepts" not in result.output


def test_uninitialized_setup_and_guide_explain_review_queue(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    client = TestClient(create_app(cfg.WikiPaths(tmp_path)))

    setup = client.get("/setup")
    assert setup.status_code == 200
    assert "candidate review queue" in setup.text
    assert "routing rules + schema" in setup.text
    assert "low-confidence review queue" not in setup.text
    assert "rules and taxonomy" not in setup.text

    guide = client.get("/guide")
    assert guide.status_code == 200
    assert "classify candidates as entities, concepts, or review items" in guide.text
    assert "review queue for ambiguous or externally owned candidates" in guide.text
    assert "matching concepts/entities" not in guide.text
