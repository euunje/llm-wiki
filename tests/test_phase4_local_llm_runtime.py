"""Regression tests for Phase 4 local OpenAI-compatible runtime integration."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from llm_wiki import config as cfg
from llm_wiki import lint, page_writer, search
from llm_wiki.llm import ChatMessage, LLMError, OllamaClient


class _FakeResponse:
    def __init__(self, data: dict):
        self._data = data
        self.text = json.dumps(data)

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _CapturingHttpClient:
    def __init__(self):
        self.payloads = []
        self.headers = []
        self.urls = []

    def post(self, url, *, json=None, headers=None):
        self.urls.append(url)
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
    assert fake_http.urls[0] == "http://192.168.1.31:1234/v1/chat/completions"
    assert fake_http.payloads[0]["response_format"] == {"type": "text"}
    assert fake_http.headers[0]["Authorization"] == "Bearer local-secret"


def test_openai_local_normalizes_missing_v1_base_url(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "local-secret")
    client = OllamaClient(
        host="http://192.168.1.31:1234",
        model="google/gemma-4-26b-a4b-qat",
        provider="openai-local",
    )
    fake_http = _CapturingHttpClient()
    client._client = fake_http

    result = client.chat([ChatMessage("user", "Return JSON")], json_mode=True)

    assert result == '{"ok": true}'
    assert client.host == "http://192.168.1.31:1234/v1"
    assert fake_http.urls[0] == "http://192.168.1.31:1234/v1/chat/completions"


def test_openai_local_200_error_json_raises_llm_error(monkeypatch):
    class _ErrorHttpClient:
        def post(self, url, *, json=None, headers=None):
            return _FakeResponse({"error": {"message": "Unexpected endpoint or method. (POST /chat/completions). Returning 200 anyway"}})

    monkeypatch.setenv("LOCAL_LLM_API_KEY", "local-secret")
    client = OllamaClient(
        host="http://192.168.1.31:1234/v1",
        model="google/gemma-4-26b-a4b-qat",
        provider="openai-local",
    )
    client._client = _ErrorHttpClient()

    try:
        client.chat([ChatMessage("user", "Return JSON")], json_mode=True)
    except LLMError as exc:
        assert "Unexpected endpoint or method" in str(exc)
    else:
        raise AssertionError("Expected LLMError")


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


def test_strip_llm_noise_removes_delimiterless_frontmatter_preamble():
    raw = """title: \"Claude Code\"
type: entity
tags: [ai-coding-agent, token-overhead]
created: 2026-07-13
updated: 2026-07-13
sources: [\"sources/claude-code-vs-opencode-token-overhead.md\"]
confidence: high

# Claude Code

Claude Code is an AI coding agent that incurs [[concepts/token-overhead]].
"""

    cleaned = page_writer.strip_llm_noise(raw)

    assert cleaned.startswith("# Claude Code")
    assert "title:" not in cleaned.split("# Claude Code", 1)[0]
    assert "confidence: high" not in cleaned.split("# Claude Code", 1)[0]
    assert "[[concepts/token-overhead]]" in cleaned


def test_qmd_uri_hits_hydrate_against_mapped_page_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    root = tmp_path / "vault"
    concept_dir = root / "20. Wiki" / "21. Concepts"
    concept_dir.mkdir(parents=True)
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
                    "page_dirs": {"concepts": "20. Wiki/21. Concepts"},
                    "files": {"config": str(config_path), "state_db": str(runtime / "state.sqlite")},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_WIKI_CONFIG", str(config_path))
    paths = cfg.WikiPaths(root)
    (concept_dir / "token-overhead.md").write_text("# Token Overhead\n\nToken costs.", encoding="utf-8")
    hit = search._hit_from_dict(
        {
            "file": "qmd://llm-wiki-pages/21-Concepts/token-overhead.md",
            "title": "Token Overhead",
            "score": 0,
        }
    )

    assert hit.collection == "llm-wiki-pages"
    assert hit.path == "21-Concepts/token-overhead.md"
    assert "Token costs" in search._read_full_content(paths, hit)
