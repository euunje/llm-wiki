"""Regression tests for Phase 1 runtime config, MCP, and changelog changes."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from llm_wiki import config as cfg
from llm_wiki.webapp.main import create_app
from llm_wiki.webapp.routes import changelog_store
from llm_wiki.webapp.routes.dashboard import _collect_stats
from llm_wiki.webapp.routes.mcp import handle_mcp_request


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_external_config_path_can_live_outside_vault(monkeypatch, tmp_path):
    vault_root = tmp_path / "vault"
    runtime = tmp_path / "agent" / "llm-wiki" / "vault-runtime"
    external_config = runtime / "config.yml"
    _write_config(
        external_config,
        {
            "paths": {
                "root": str(vault_root),
                "internal_dir": str(runtime),
                "wiki_dir": "20. Wiki",
                "page_dirs": {"concepts": "20. Wiki/21. Concepts"},
                "files": {"state_db": str(runtime / "state.sqlite")},
            }
        },
    )

    monkeypatch.setenv("LLM_WIKI_CONFIG", str(external_config))
    paths = cfg.WikiPaths(vault_root)

    assert cfg.external_config_path() == external_config.resolve()
    assert cfg.find_wiki_root() == vault_root.resolve()
    assert paths.config_file == external_config.resolve()
    assert paths.is_initialized()
    assert paths.internal == runtime.resolve()
    assert paths.concepts == (vault_root / "20. Wiki/21. Concepts").resolve()


def test_config_file_uses_external_path_before_file_exists(monkeypatch, tmp_path):
    external_config = tmp_path / "runtime" / "config.yml"
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(external_config))

    paths = cfg.WikiPaths(tmp_path / "vault")

    assert paths.config_file == external_config.resolve()
    assert not paths.is_initialized()


def test_mcp_uses_configured_page_dirs_and_graph_tool(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = cfg.WikiPaths(tmp_path)
    tools_result = handle_mcp_request(paths, {"jsonrpc": "2.0", "id": 0, "method": "tools/list"})
    assert "get_graph_data" in {tool["name"] for tool in tools_result["result"]["tools"]}
    _write_config(
        tmp_path / ".wiki" / "config.yml",
        {
            "paths": {
                "wiki_dir": "20. Wiki",
                "page_dirs": {
                    "concepts": "20. Wiki/21. Concepts",
                    "synthesis": "30. Queries",
                },
            }
        },
    )
    concepts = tmp_path / "20. Wiki" / "21. Concepts"
    queries = tmp_path / "30. Queries"
    concepts.mkdir(parents=True)
    queries.mkdir(parents=True)
    (concepts / "alpha.md").write_text("# Alpha\n\nlinks to [[30. Queries/beta]]", encoding="utf-8")
    (queries / "beta.md").write_text("# Beta\n\nalpha keyword", encoding="utf-8")

    list_result = handle_mcp_request(
        paths,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_wiki_pages", "arguments": {}}},
    )
    list_text = list_result["result"]["content"][0]["text"]
    assert "20. Wiki/21. Concepts/alpha.md" in list_text
    assert "30. Queries/beta.md" in list_text

    page_result = handle_mcp_request(
        paths,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_page_content", "arguments": {"path": "30. Queries/beta.md"}}},
    )
    assert "alpha keyword" in page_result["result"]["content"][0]["text"]

    graph_result = handle_mcp_request(
        paths,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_graph_data", "arguments": {}}},
    )
    graph_data = json.loads(graph_result["result"]["content"][0]["text"])
    assert set(graph_data) == {"nodes", "edges", "stats"}
    assert graph_data["stats"]["node_count"] >= 2


def test_dashboard_last_updated_uses_configured_page_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    runtime = tmp_path / "runtime"
    paths = cfg.WikiPaths(tmp_path / "vault")
    _write_config(
        paths.root / ".wiki" / "config.yml",
        {
            "paths": {
                "wiki_dir": "20. Wiki",
                "internal_dir": str(runtime),
                "page_dirs": {
                    "synthesis": "30. Queries",
                    "non_categories": "00. Inbox/_Review",
                },
            }
        },
    )
    db_path = cfg.WikiPaths(paths.root).state_db
    # Make DB stats available without forcing dashboard to create vault content.
    from llm_wiki import db
    db.init_db(db_path)

    synthesis = paths.root / "30. Queries"
    synthesis.mkdir(parents=True)
    (synthesis / "answer.md").write_text("---\ntitle: Answer\ntype: synthesis\ncreated: 2026-07-13\n---\n\nBody\n", encoding="utf-8")

    stats = _collect_stats(cfg.WikiPaths(paths.root))

    assert stats["pages"]["synthesis"] == 1
    assert stats["last_updated"] is not None


def test_changelog_store_lives_under_internal_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    runtime = tmp_path / "runtime"
    paths = cfg.WikiPaths(tmp_path / "vault")
    _write_config(
        paths.root / ".wiki" / "config.yml",
        {"paths": {"internal_dir": str(runtime)}},
    )

    entry = changelog_store.create_change(
        paths=paths,
        changed_by="tester",
        change_type="config",
        before_state={"enabled": False},
        after_state={"enabled": True},
        reason="enable test config",
        source_file="config.yml",
        affected_service="webapp",
        rollback_available=True,
        verification_evidence=None,
        linked_wiki_pages=["20. Wiki/21. Concepts/example.md"],
        status="applied",
    )

    store_file = runtime / "changelog" / "change_history.json"
    assert store_file.exists()
    assert not str(store_file).startswith(str(paths.root / "20. Wiki"))
    assert changelog_store.get_change(paths, entry["change_id"])["reason"] == "enable test config"
    assert changelog_store.list_changes(paths, change_type="config")
    assert changelog_store.list_changes(paths, status="applied")
    assert changelog_store.list_changes(paths, status="pending") == []

    verified = changelog_store.update_change_status(
        paths,
        entry["change_id"],
        "verified",
        verification_evidence="pytest",
    )
    assert verified is not None
    assert verified["status"] == "verified"
    assert verified["verification_evidence"] == "pytest"


def test_changelog_api_routes(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = cfg.WikiPaths(tmp_path)
    _write_config(tmp_path / ".wiki" / "config.yml", {"paths": {"internal_dir": "runtime"}})
    client = TestClient(create_app(paths))

    assert client.get("/changelog").status_code == 200
    empty = client.get("/api/changelog")
    assert empty.status_code == 200
    assert empty.json() == {"changes": [], "total": 0}

    payload = {
        "changed_by": "tester",
        "change_type": "config",
        "before_state": None,
        "after_state": {"enabled": True},
        "reason": "route coverage",
        "source_file": "config.yml",
        "affected_service": "webapp",
        "rollback_available": False,
        "linked_wiki_pages": [],
        "status": "applied",
    }
    created = client.post("/api/changelog", json=payload)
    assert created.status_code == 201
    change_id = created.json()["change"]["change_id"]

    filtered = client.get("/api/changelog", params={"change_type": "config", "status": "applied"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    verified = client.post(
        f"/api/changelog/verify/{change_id}",
        json={"verification_evidence": "route smoke"},
    )
    assert verified.status_code == 200
    assert verified.json()["change"]["status"] == "verified"
