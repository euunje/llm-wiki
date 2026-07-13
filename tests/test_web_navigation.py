"""Regression tests for web navigation consistency."""

from __future__ import annotations

from fastapi.testclient import TestClient

from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def test_jobs_page_uses_shared_sidebar_navigation(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "Jobs" in response.text
    for label in [
        "Dashboard",
        "Sources",
        "Inbox",
        "Ingest",
        "Jobs",
        "Query",
        "Lint",
        "Graph",
        "Changelog",
        "Logs",
        "Settings",
    ]:
        assert f">{label}<" in response.text
    assert "Start an ingest run" in response.text
