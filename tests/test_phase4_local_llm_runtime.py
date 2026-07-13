"""Regression tests for Phase 4 local OpenAI-compatible runtime integration."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from llm_wiki import config as cfg
from llm_wiki import lint
from llm_wiki.llm import ChatMessage, OllamaClient


class _FakeResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _CapturingHttpClient:
    def __init__(self):
        self.payloads = []
        self.headers = []

    def post(self, url, *, json=None, headers=None):
        self.payloads.append(json)
        self.headers.append(headers or {})
        return _FakeResponse({"choices": [{"message": {"content": "{\"ok\": true}"}}]})


def test_openai_local_reads_local_llm_api_key_from_hermes_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    env_dir = home / ".hermes"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("LOCAL_LLM_API_KEY=local-secret\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = OllamaClient(
        host="http://192.168.1.31:1234/v1",
        model="google/gemma-4-26b-a4b-qat",
        provider="openai-local",
    )

    assert client.api_key == "local-secret"


def test_openai_local_json_mode_uses_text_response_format(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "local-secret")
    client = OllamaClient(
        host="http://192.168.1.31:1234/v1",
        model="google/gemma-4-26b-a4b-qat",
        provider="openai-local",
    )
    fake_http = _CapturingHttpClient()
    client._client = fake_http

    result = client.chat([ChatMessage("user", "Return JSON")], json_mode=True)

    assert result == '{"ok": true}'
    assert fake_http.payloads[0]["response_format"] == {"type": "text"}
    assert fake_http.headers[0]["Authorization"] == "Bearer local-secret"


def test_lint_resolves_source_refs_through_mapped_page_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    root = tmp_path / "vault"
    (root / "20. Wiki" / "20. Sources").mkdir(parents=True)
    (root / "20. Wiki" / "21. Concepts").mkdir(parents=True)
    (root / "20. Wiki" / "22. Entities").mkdir(parents=True)
    (root / "30. Queries").mkdir(parents=True)
    (root / "00. Inbox" / "_Review").mkdir(parents=True)
    (root / "10. Raw Sources").mkdir(parents=True)

    config_path = runtime / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "paths": {
                    "root": str(root),
                    "raw_dir": "10. Raw Sources",
                    "wiki_dir": "20. Wiki",
                    "internal_dir": str(runtime),
                    "page_dirs": {
                        "sources": "20. Wiki/20. Sources",
                        "concepts": "20. Wiki/21. Concepts",
                        "entities": "20. Wiki/22. Entities",
                        "synthesis": "30. Queries",
                        "non_categories": "00. Inbox/_Review",
                    },
                    "files": {
                        "config": str(config_path),
                        "state_db": str(runtime / "state.sqlite"),
                    },
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(config_path))
    paths = cfg.WikiPaths(root)

    (paths.page_dir("sources") / "claude-code-vs-opencode-token-overhead.md").write_text(
        "---\ntitle: Source\ntype: source\ncreated: 2026-07-13\n---\n\n"
        "# Source\n\n[[concepts/mcp]]\n",
        encoding="utf-8",
    )
    (paths.page_dir("concepts") / "mcp.md").write_text(
        "---\ntitle: MCP\ntype: concept\ncreated: 2026-07-13\nupdated: 2026-07-13\n"
        "sources:\n- sources/claude-code-vs-opencode-token-overhead\n---\n\n"
        "# MCP\n\n[[sources/claude-code-vs-opencode-token-overhead]]\n",
        encoding="utf-8",
    )

    report = lint.run_lint(paths)

    assert report.pages_checked == 2
    assert not report.issues
