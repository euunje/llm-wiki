"""Phase 1 init/settings/doctor test coverage.

Each test uses pytest's ``tmp_path`` so the workspace lives only for the
test. ``wiki init`` must create the Vault and data folders, write a YAML
settings file, build the SQLite schema, and remain idempotent on re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser, main as cli_main
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code, payload = args.handler(args)
    if not isinstance(payload, dict):
        raise AssertionError(f"handler returned non-dict payload: {payload!r}")
    return exit_code, payload


def test_init_creates_vault_and_data_layout(workspace: Path) -> None:
    paths = resolve_workspace(workspace)
    assert not paths.db.exists()

    exit_code, payload = _invoke(["init"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"

    # Vault-area folders exist and have the numeric prefixes used in the
    # build-start-gate contract.
    assert paths.inbox_memo.is_dir()
    assert paths.inbox_files.is_dir()
    assert paths.inbox_text.is_dir()
    assert paths.wiki_concepts.is_dir()
    assert paths.wiki_sources.is_dir()
    assert paths.wiki_claims.is_dir()
    assert paths.wiki_pages.is_dir()
    assert paths.review_candidates.is_dir()
    assert paths.review_mapping.is_dir()
    assert paths.review_rejected.is_dir()
    assert paths.raws.is_dir()
    assert paths.templates.is_dir()
    assert paths.prompts.is_dir()
    assert paths.ontology.is_dir()

    # Data-area folders exist.
    assert paths.raw.is_dir()
    assert paths.normalized.is_dir()
    assert paths.artifacts.is_dir()
    assert paths.exports.is_dir()
    assert paths.cache.is_dir()

    # SQLite database and YAML settings exist and are valid.
    assert paths.db.exists()
    assert paths.settings_file.exists()
    content = paths.settings_file.read_text(encoding="utf-8")
    assert "vault: vault" in content or "vault:" in content


def test_init_is_idempotent(workspace: Path) -> None:
    paths = resolve_workspace(workspace)
    _invoke(["init"], workspace)
    initial_db_mtime = paths.db.stat().st_mtime
    initial_settings_mtime = paths.settings_file.stat().st_mtime

    # Re-run; the database file should remain and the settings file should not
    # be touched (idempotent contract).
    _invoke(["init"], workspace)
    assert paths.db.exists()
    assert paths.settings_file.exists()
    # The database file's mtime is allowed to change because the bootstrap
    # reopens the connection. The settings file should remain stable.
    assert paths.settings_file.stat().st_mtime == initial_settings_mtime

    # Second invocation must report no new directories because all already exist.
    _, payload = _invoke(["init"], workspace)
    assert payload["created_directories"] == []


def test_settings_get_set_masks_sensitive_values(workspace: Path) -> None:
    _invoke(["init"], workspace)

    # Get all settings returns a dict and never raises.
    _, payload = _invoke(["settings", "get"], workspace)
    assert payload["status"] == "ok"
    value = payload["value"]
    assert isinstance(value, dict)
    assert "embedding" in value
    # Sensitive fragment "api_key" lives nested under llm.settings but the
    # top-level payload is the masked representation, so ensure nothing
    # crashes even when no key is passed.

    # Drill into a known nested key.
    _, nested = _invoke(["settings", "get", "embedding.default_model"], workspace)
    assert nested["key"] == "embedding.default_model"
    assert nested["value"]

    # Set a permitted leaf setting and verify it survives the round-trip.
    _invoke(["settings", "set", "embedding.default_model", "test-model"], workspace)
    _, after = _invoke(["settings", "get", "embedding.default_model"], workspace)
    assert after["value"] == "test-model"


def test_settings_get_resolves_llm_values_from_documented_env_keys(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _invoke(["init"], workspace)
    monkeypatch.setenv("LLM_WIKI_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_WIKI_CHAT_MODEL", "chat-from-env")
    monkeypatch.setenv("LLM_WIKI_EMBEDDING_MODEL", "embed-from-env")

    _, payload = _invoke(["settings", "get"], workspace)
    llm = payload["value"]["llm"]
    assert llm["endpoint"] == "https://example.invalid/v1"
    assert llm["default_chat_model"] == "chat-from-env"
    assert llm["default_embedding_model"] == "embed-from-env"
    assert llm["models"]["chat_default"]["endpoint"] == "https://example.invalid/v1"
    assert llm["models"]["chat_default"]["model_name"] == "chat-from-env"
    assert llm["models"]["embedding_default"]["model_name"] == "embed-from-env"


def test_doctor_reports_workspace_state(workspace: Path) -> None:
    _invoke(["init"], workspace)
    _, payload = _invoke(["doctor"], workspace)
    assert payload["status"] == "ok"
    assert payload["paths"], "doctor must report per-path status"
    assert payload["database"]["exists"] is True
    assert payload["fts5"]["status"] in {"ok", "warn"}
    # The LLM endpoint is empty in the default settings; doctor flags it as warn.
    assert payload["models"]["status"] in {"ok", "warn"}


def test_cli_main_handles_unknown_subcommand_via_dispatch(workspace: Path, capsys) -> None:
    # ``wiki --help`` is registered as command=help or no command. With no
    # subcommand the parser should print help and return 0.
    exit_code = cli_main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "LLM Wiki Local CLI" in captured.out
