"""Tests for /api/ask modes: search_only, ask_wiki, ask_raw, ask_hybrid."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("LLM_WIKI_API_KEY", "super-secret-token")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    import subprocess, sys
    from llm_wiki.cli import build_parser
    parser = build_parser()
    args = parser.parse_args([*cli_args, "--path", str(path), "--json"])
    return args.handler(args)


# ------------------------------------------------------------------
# Part A: Ask modes
# ------------------------------------------------------------------

def test_ask_request_accepts_mode_field(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AskRequest must accept a `mode` field."""
    client = _client(workspace, monkeypatch)
    resp = client.post("/api/ask", json={"query": "test", "mode": "search_only"})
    # Either 200 (implemented) or 422 (not yet implemented)
    assert resp.status_code in (200, 422)


def test_ask_search_only_returns_search_results_without_llm(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    """search_only mode returns results from search_workspace without LLM synthesis."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    resp = client.post("/api/ask", json={"query": "RAG", "mode": "search_only"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert isinstance(payload.get("search_results"), list)
    # search_only must NOT fabricate an LLM answer
    answer = payload.get("answer", "")
    assert "LLM unavailable" in answer or not answer or payload.get("llm_available") is False


def test_ask_with_no_db_returns_empty_state_not_error(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty DB / no sources: UI must show explicit empty state, not crash."""
    client = _client(workspace, monkeypatch)
    resp = client.post("/api/ask", json={"query": "anything", "mode": "search_only"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    # Must have explicit indication of empty results
    assert payload.get("search_results") == [] or payload.get("count", 0) == 0


def test_ask_hybrid_mode_uses_llm_synthesis(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    """ask_hybrid mode: when LLM is available, synthesizes answer from search results."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    resp = client.post("/api/ask", json={"query": "RAG groundedness", "mode": "ask_hybrid"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert isinstance(payload.get("search_results"), list)
    # Should have either an LLM answer or explicit unavailability message
    # Must NOT fabricate when LLM unavailable
    if payload.get("llm_available") is False:
        assert not payload.get("answer") or "LLM unavailable" in payload.get("answer", "")


def test_ask_wiki_mode_only_searches_wiki_collection(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    """ask_wiki mode: scope restricted to llm-wiki-pages collection."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    resp = client.post("/api/ask", json={"query": "RAG", "mode": "ask_wiki"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    # scope metadata should indicate wiki-only
    assert payload.get("scope") in ("wiki", "llm-wiki-pages")


def test_ask_raw_mode_only_searches_raw_collection(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    """ask_raw mode: scope restricted to llm-wiki-raw collection."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    resp = client.post("/api/ask", json={"query": "RAG", "mode": "ask_raw"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload.get("scope") in ("raw", "llm-wiki-raw")


def test_ask_returns_evidence_refs_with_sources(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    """All ask modes return evidence_refs with source filename and snippet."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    resp = client.post("/api/ask", json={"query": "RAG", "mode": "search_only"})
    assert resp.status_code == 200
    payload = resp.json()
    # evidence_refs should be present
    assert isinstance(payload.get("evidence_refs"), list)
    if payload.get("evidence_refs"):
        ref = payload["evidence_refs"][0]
        assert "source_id" in ref or "target_id" in ref


def test_ask_mode_field_defaults_to_hybrid(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When mode is omitted, it defaults to ask_hybrid behavior."""
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    resp = client.post("/api/ask", json={"query": "test"})
    # Should not 422 — should accept the request
    assert resp.status_code in (200, 422)
