from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.config.settings import load_settings, save_settings
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


def _set_fake_home(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home_dir = workspace.parent / f"{workspace.name}-home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    return home_dir


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
    assert payload["query"] == "RAG에서 groundedness가 왜 중요한가?"
    # LLM env vars are unset in this test run — answer may be empty, no fabrication allowed
    assert "llm_available" in payload
    assert payload["llm_available"] is False
    assert isinstance(payload["evidence_refs"], list)
    assert isinstance(payload["search_results"], list)
    assert "vector" in payload["search_metadata"]


def test_api_queries_save_writes_frontmatter_and_avoids_overwrite(workspace: Path, monkeypatch: pytest.MonkeyPatch, samples_dir: Path) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client = _client(workspace, monkeypatch)
    human_vault = home_dir / "vault"
    for folder in [
        human_vault / "00_Inbox",
        human_vault / "10_Wiki",
        human_vault / "20_Review",
        human_vault / "30. Queries",
        human_vault / "90_Settings",
    ]:
        folder.mkdir(parents=True, exist_ok=True)
    paths = resolve_workspace(workspace)
    settings = load_settings(paths.settings_file, resolve_env=False)
    settings["workspace"] = {"human_vault": "~/vault", "system_data": "data"}
    settings["vault"] = {"vault_path": "~/vault", "role_map": {"queries": "~/vault/30. Queries"}}
    settings.setdefault("paths", {})["vault"] = "~/vault"
    save_settings(paths.settings_file, settings)

    _invoke(["init"], workspace)
    source_id = _invoke(["ingest", str(samples_dir / "rag.md")], workspace)[1]["source_id"]
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    ask = client.post("/api/ask", json={"query": "RAG groundedness 요약"})
    ask_payload = ask.json()
    response = client.post(
        "/api/queries/save",
        json={
            "query": ask_payload["query"],
            "answer": ask_payload["answer"],
            "scope": "wiki",
            "evidence": ask_payload["evidence_refs"],
            "search_results": ask_payload["search_results"],
            "title": "RAG groundedness 요약",
            "note": "테스트 저장",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    saved_file = Path(payload["saved_path"])
    assert saved_file.parent == human_vault / "30. Queries"
    assert saved_file.name.endswith("-rag-groundedness.md")
    document = yaml.safe_load(saved_file.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert document["type"] == "query_answer"
    assert document["status"] == "saved"
    assert document["query"] == ask_payload["query"]
    assert document["scope"] == "wiki"
    assert document["source"] == "llm-wiki-web"
    assert document["tags"][:2] == ["llm-wiki", "query"]
    assert document["generation"]["saved_by"] == "web_user"
    assert isinstance(document["evidence"], list)

    second = client.post(
        "/api/queries/save",
        json={
            "query": ask_payload["query"],
            "answer": ask_payload["answer"],
            "scope": "wiki",
            "search_results": ask_payload["search_results"],
            "title": "RAG groundedness 요약",
        },
    )
    assert second.status_code == 200
    assert second.json()["filename"].endswith("-rag-groundedness-2.md")

    korean_title = client.post(
        "/api/queries/save",
        json={
            "query": "한국어 제목 저장 확인",
            "answer": "저장됨",
            "scope": "wiki",
            "title": "한국어 제목 저장 확인",
            "tags": ["custom"],
        },
    )
    assert korean_title.status_code == 200
    assert "한국어-제목-저장-확인" in korean_title.json()["filename"]
    korean_doc = yaml.safe_load(Path(korean_title.json()["saved_path"]).read_text(encoding="utf-8").split("---\n", 2)[1])
    assert korean_doc["tags"][:2] == ["llm-wiki", "query"]


def test_api_queries_save_rejects_queries_path_outside_home_vault(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client = _client(workspace, monkeypatch)
    human_vault = home_dir / "vault"
    human_vault.mkdir(parents=True, exist_ok=True)
    outside_dir = home_dir / "other-queries"
    outside_dir.mkdir(parents=True, exist_ok=True)
    paths = resolve_workspace(workspace)
    settings = load_settings(paths.settings_file, resolve_env=False)
    settings["workspace"] = {"human_vault": "~/vault", "system_data": "data"}
    settings["vault"] = {"vault_path": "~/vault", "role_map": {"queries": "~/other-queries"}}
    settings.setdefault("paths", {})["vault"] = "~/vault"
    save_settings(paths.settings_file, settings)

    response = client.post(
        "/api/queries/save",
        json={"query": "test", "answer": "answer", "scope": "wiki"},
    )

    assert response.status_code == 422
