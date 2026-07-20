from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    parser = build_parser()
    args = parser.parse_args([*cli_args, "--path", str(path), "--json"])
    return args.handler(args)


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client


def test_api_ask_returns_answer_evidence_and_search_metadata(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    client = _client(workspace, monkeypatch)
    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    response = client.post("/api/ask", json={"query": "RAG에서 groundedness가 왜 중요한가?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"]
    assert isinstance(payload["evidence_refs"], list)
    assert "vector" in payload["search_metadata"]
