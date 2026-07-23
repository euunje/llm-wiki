"""Phase 1 models, route, placeholder, ops command tests."""

from __future__ import annotations

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.config import load_settings, save_settings
from llm_wiki.db.schema import connect
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _ensure_init(workspace: Path) -> None:
    _invoke(["init"], workspace)


def _ingest(workspace: Path, sample: Path) -> str:
    _, payload = _invoke(["ingest", str(sample)], workspace)
    assert payload["status"] == "ok"
    return payload["source_id"]


def test_models_list_returns_configured_entries(workspace: Path) -> None:
    _ensure_init(workspace)
    _, payload = _invoke(["models", "list"], workspace)
    assert payload["status"] == "ok"
    models = payload["models"]
    assert any(model["id"] == "chat_default" for model in models)
    assert any(model["id"] == "embedding_default" for model in models)


def test_models_list_returns_local_embedding_folder_entries(workspace: Path) -> None:
    _ensure_init(workspace)
    model_root = workspace / "models" / "embeddings"
    (model_root / "local-embed-a").mkdir(parents=True)
    (model_root / ".hidden").mkdir()
    settings = load_settings(resolve_workspace(workspace).settings_file, resolve_env=False)
    settings["embedding"]["model_root"] = "models/embeddings"
    settings["embedding"]["default_model"] = "local-embed-a"
    save_settings(resolve_workspace(workspace).settings_file, settings)

    _, payload = _invoke(["models", "list"], workspace)

    assert payload["embedding_models"] == [
        {
            "id": "local-embed-a",
            "model_name": "local-embed-a",
            "display_name": "local-embed-a",
            "provider": "local_embedding_folder",
            "capability": "embedding",
            "path": str(model_root / "local-embed-a"),
            "root": str(model_root),
            "source": "configured_default",
        }
    ]
    embedding_slot = next(model for model in payload["models"] if model["id"] == "embedding_default")
    assert embedding_slot["provider"] == "local_embedding_folder"
    assert embedding_slot["request_format"] == "local_embedding_folder"
    assert embedding_slot["configured"] is True


def test_models_test_records_blocked_artifact_when_not_configured(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default settings have empty ``endpoint`` so ``models test`` must record a
    blocked artifact instead of attempting a network call."""

    monkeypatch.delenv("LOCAL_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LOCAL_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("LLM_WIKI_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_WIKI_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LLM_WIKI_EMBEDDING_MODEL", raising=False)
    _ensure_init(workspace)
    _, payload = _invoke(["models", "test", "chat_default"], workspace)
    # Default exit code for the blocked branch is 3 (external dependency).
    assert payload["status"] == "blocked"
    assert payload["result"] == "blocked"
    assert "endpoint" in payload["reason"].lower() or "model_name" in payload["reason"].lower()
    assert payload["model"]["endpoint_configured"] is False
    # Phase 1 must leave a trace: an artifact file under data/artifacts/.
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()
    stored = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert stored["status"] == "blocked"


def test_models_test_uses_documented_env_fallbacks_without_keyerror(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ensure_init(workspace)
    monkeypatch.delenv("LOCAL_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LOCAL_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("LLM_WIKI_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_WIKI_CHAT_MODEL", "chat-from-env")
    monkeypatch.setenv("LLM_WIKI_EMBEDDING_MODEL", "embed-from-env")
    synthetic_key = "sk-test-synthetic-do-not-leak"
    monkeypatch.setenv("LLM_WIKI_API_KEY", synthetic_key)

    exit_code, payload = _invoke(["models", "test", "chat_default"], workspace)
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["model"]["endpoint_configured"] is True
    assert payload["model"]["model_name_configured"] is True
    assert payload["model"]["api_key_present"] is True
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()


def test_models_test_configured_failure_does_not_leak_credentials(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BL-1 regression guard.

    Configured `models test` failure must never include the synthetic
    API key (or its `Bearer ` form) in the CLI payload, the artifact
    file, the artifact DB row, the job `error_json`, or the
    `agent_runs.error_json`. Booleans are the only allowed surface.
    """

    _ensure_init(workspace)
    monkeypatch.delenv("LOCAL_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LOCAL_LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("LLM_WIKI_LLM_ENDPOINT", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_WIKI_CHAT_MODEL", "chat-from-env")
    monkeypatch.setenv("LLM_WIKI_EMBEDDING_MODEL", "embed-from-env")
    synthetic_key = "sk-test-synthetic-do-not-leak"
    monkeypatch.setenv("LLM_WIKI_API_KEY", synthetic_key)

    exit_code, payload = _invoke(["models", "test", "chat_default"], workspace)
    assert exit_code == 1
    assert payload["status"] == "failed"

    # 1. CLI payload: no raw key, no Bearer substring.
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert synthetic_key not in payload_text
    assert "Bearer " + synthetic_key not in payload_text
    assert "Bearer ***" not in payload_text or "Bearer ***" in payload_text  # allow generic redaction only
    # The configured-failure payload must use the credential-safe `request` summary.
    request_summary = payload.get("request", {})
    assert set(request_summary.keys()) <= {"endpoint_configured", "model_name_configured", "api_key_present"}
    assert all(isinstance(v, bool) for v in request_summary.values())

    # 2. Artifact file: same constraints, plus the file exists and parses as JSON.
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()
    artifact_text = artifact_path.read_text(encoding="utf-8")
    assert synthetic_key not in artifact_text
    assert "Bearer " + synthetic_key not in artifact_text

    # 3. SQLite-side: artifact row, job error_json, agent_run error_json contain no raw key.
    from llm_wiki.db.schema import connect
    from llm_wiki.workspace import resolve_workspace

    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        artifact_row = conn.execute(
            "SELECT content_hash, metadata_json FROM artifacts WHERE id = ?",
            (payload["artifact_id"],),
        ).fetchone()
        assert artifact_row is not None

        job_row = conn.execute(
            "SELECT error_json FROM jobs WHERE id = ?",
            (payload["job_id"],),
        ).fetchone()
        assert job_row is not None
        job_error_text = job_row[0] or ""

        run_row = conn.execute(
            "SELECT error_json FROM agent_runs WHERE id = ?",
            (payload["run_id"],),
        ).fetchone()
        assert run_row is not None
        run_error_text = run_row[0] or ""

        for label, haystack in (
            ("jobs.error_json", job_error_text),
            ("agent_runs.error_json", run_error_text),
        ):
            assert synthetic_key not in haystack, f"synthetic key leaked into {label}"
            assert "Bearer " + synthetic_key not in haystack, f"Bearer token leaked into {label}"
    finally:
        conn.close()


def test_models_test_succeeds_against_ephemeral_openai_compatible_mock(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use a dynamically bound local test server to validate the success path.

    The reusable source has no hardcoded host/port. This test injects the
    ephemeral endpoint into the workspace settings only for validation.
    """

    monkeypatch.delenv("LLM_WIKI_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            length = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(length)
            payload = {
                "id": "mock-chat-completion",
                "choices": [{"message": {"role": "assistant", "content": "OK"}}],
            }
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        settings["llm"]["models"]["chat_default"]["endpoint"] = endpoint
        settings["llm"]["models"]["chat_default"]["model_name"] = "mock-chat"
        save_settings(paths.settings_file, settings)

        exit_code, payload = _invoke(["models", "test", "chat_default"], workspace)
        assert exit_code == 0
        assert payload["status"] == "ok"
        assert payload["result"] == "ok"
        assert payload["model"]["endpoint_configured"] is True
        assert payload["model"]["model_name_configured"] is True
        assert payload["model"]["api_key_present"] is False
        artifact_path = workspace / payload["artifact_path"]
        assert artifact_path.exists()
        stored = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert stored["status"] == "ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_list_provider_models_normalizes_lmstudio_custom_and_ollama_endpoints(workspace: Path) -> None:
    seen_paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            seen_paths.append(self.path)
            if self.path == "/api/tags":
                payload = {"models": [{"name": "llama3:latest"}]}
            else:
                payload = {"data": [{"id": "chat-model"}, {"id": "text-embedding-nomic-embed-text-v1.5"}]}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        from llm_wiki.llm.models import list_provider_models

        settings["llm"]["provider"] = "lmstudio"
        settings["llm"]["endpoint"] = f"http://127.0.0.1:{server.server_port}/v1"
        save_settings(paths.settings_file, settings)
        lmstudio_models = list_provider_models(paths)
        assert seen_paths[-1] == "/v1/models"
        assert [m["model_name"] for m in lmstudio_models] == ["chat-model", "text-embedding-nomic-embed-text-v1.5"]
        assert lmstudio_models[0]["capability"] == "chat"
        assert lmstudio_models[1]["capability"] == "embedding"

        settings["llm"]["provider"] = "custom"
        settings["llm"]["endpoint"] = f"http://127.0.0.1:{server.server_port}"
        save_settings(paths.settings_file, settings)
        list_provider_models(paths)
        assert seen_paths[-1] == "/v1/models"

        settings["llm"]["provider"] = "ollama"
        settings["llm"]["endpoint"] = f"http://127.0.0.1:{server.server_port}/api"
        save_settings(paths.settings_file, settings)
        ollama_models = list_provider_models(paths)
        assert seen_paths[-1] == "/api/tags"
        assert ollama_models[0]["model_name"] == "llama3:latest"

        from llm_wiki.llm.models import _request_endpoint

        assert _request_endpoint(settings["llm"]["endpoint"], "openai_chat").endswith("/v1/chat/completions")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_call_json_task_omits_max_tokens_by_default(workspace: Path) -> None:
    """Think-Off local LLMs should not be capped by an implicit 1600 token limit."""

    seen_requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            length = int(self.headers.get("Content-Length", "0") or "0")
            seen_requests.append(json.loads(self.rfile.read(length).decode("utf-8")))
            payload = {
                "id": "mock-chat-completion",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"task_type":"extract_claims","claim_candidates":[],"node_candidates":[]}',
                        }
                    }
                ],
            }
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        settings["llm"]["models"]["chat_default"]["endpoint"] = endpoint
        settings["llm"]["models"]["chat_default"]["model_name"] = "mock-chat"
        save_settings(paths.settings_file, settings)

        from llm_wiki.llm.chat import call_json_task

        result = call_json_task(
            paths,
            model_id="chat_default",
            system_prompt="Return JSON.",
            user_prompt="Return an empty candidate envelope.",
        )

        assert result["parsed_json"]["task_type"] == "extract_claims"
        assert seen_requests
        assert "max_tokens" not in seen_requests[0]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_call_json_task_prefers_v1_chat_endpoint_for_openai_compatible_base(workspace: Path) -> None:
    seen_paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            seen_paths.append(self.path)
            length = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(length)
            payload = {"choices": [{"message": {"content": '{"task_type":"extract_claims","claim_candidates":[],"node_candidates":[]}'}}]}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        settings["llm"]["models"]["chat_default"]["endpoint"] = f"http://127.0.0.1:{server.server_port}"
        settings["llm"]["models"]["chat_default"]["model_name"] = "mock-chat"
        save_settings(paths.settings_file, settings)

        from llm_wiki.llm.chat import call_json_task

        call_json_task(paths, model_id="chat_default", system_prompt="Return JSON.", user_prompt="Return JSON.")
        assert seen_paths == ["/v1/chat/completions"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_call_json_task_http_error_includes_response_body(workspace: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            length = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(length)
            data = b'{"error":"bad request details"}'
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        settings["llm"]["models"]["chat_default"]["endpoint"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        settings["llm"]["models"]["chat_default"]["model_name"] = "mock-chat"
        save_settings(paths.settings_file, settings)

        from llm_wiki.llm.chat import call_json_task

        try:
            call_json_task(paths, model_id="chat_default", system_prompt="Return JSON.", user_prompt="Return JSON.")
        except RuntimeError as exc:
            assert "HTTP Error 400" in str(exc)
            assert "bad request details" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_call_json_task_uses_llm_advanced_temperature_and_max_tokens_when_configured(workspace: Path) -> None:
    seen_requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            length = int(self.headers.get("Content-Length", "0") or "0")
            seen_requests.append(json.loads(self.rfile.read(length).decode("utf-8")))
            payload = {"choices": [{"message": {"content": '{"task_type":"extract_claims","claim_candidates":[],"node_candidates":[]}'}}]}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    _ensure_init(workspace)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        paths = resolve_workspace(workspace)
        settings = load_settings(paths.settings_file)
        settings["llm"]["advanced"] = {"temperature": 0.2, "max_tokens": 4096}
        settings["llm"]["models"]["chat_default"]["endpoint"] = endpoint
        settings["llm"]["models"]["chat_default"]["model_name"] = "mock-chat"
        save_settings(paths.settings_file, settings)

        from llm_wiki.llm.chat import call_json_task

        call_json_task(paths, model_id="chat_default", system_prompt="Return JSON.", user_prompt="Return JSON.")

        assert seen_requests
        assert seen_requests[0]["temperature"] == 0.2
        assert seen_requests[0]["max_tokens"] == 4096
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_route_get_returns_current_mapping(workspace: Path) -> None:
    _ensure_init(workspace)
    _, payload = _invoke(["route", "get"], workspace)
    assert payload["status"] == "ok"
    routes = payload["routes"]
    assert routes["extract_claims"] == "chat_default"


def test_route_set_rejects_capability_mismatch(workspace: Path) -> None:
    _ensure_init(workspace)
    from llm_wiki.cli import main as cli_main

    # embedding_default has capability "embedding"; routing a chat task to it
    # must fail with exit code 2 (user input error).
    exit_code = cli_main(
        ["route", "set", "extract_claims", "embedding_default", "--path", str(workspace)]
    )
    assert exit_code == 2


def test_extract_claims_artifact_matches_schema_contract(
    workspace: Path, samples_dir: Path
) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")

    _, payload = _invoke(["extract-claims", source_id], workspace)
    assert payload["status"] == "ok"
    assert payload["run_id"].startswith("run_")
    assert payload["job_id"].startswith("job_")
    envelope = payload["candidate_envelope"]
    assert envelope["task_type"] == "extract_claims"
    assert envelope["schema_version"] == "candidate.v1"
    assert isinstance(envelope["claim_candidates"], list)
    assert isinstance(envelope["node_candidates"], list)
    assert envelope["claim_candidates"]
    assert envelope["node_candidates"]
    assert envelope["claim_candidates"][0]["candidate_key"].startswith("claim_")
    assert envelope["node_candidates"][0]["candidate_key"].startswith("node_")
    validation = payload["validation"]
    assert validation["ok"] is True
    assert validation["errors"] == []

    # The artifact JSON is stored under data/artifacts/extract_claims/.
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()


def test_cli_exposes_only_real_user_facing_llm_commands(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")

    _, extract_payload = _invoke(["extract-claims", source_id], workspace)
    assert extract_payload["status"] == "ok"

    _, ask = _invoke(["ask", "What is RAG?"], workspace)
    assert ask["status"] == "ok"
    assert ask["answer_placeholder"]
    assert isinstance(ask["evidence_refs"], list)

    parser = build_parser()
    command_choices = parser._subparsers._group_actions[0].choices  # argparse command registry
    assert "extract-claims" in command_choices
    assert "ask" in command_choices
    for removed in ("summarize", "link", "map", "compile"):
        assert removed not in command_choices


def test_debug_repair_source_stubs_dry_run_does_not_apply_by_default(workspace: Path) -> None:
    _ensure_init(workspace)
    _, payload = _invoke(["debug-repair-source-stubs"], workspace)
    assert payload["status"] == "ok"
    assert payload["apply"] is False
    assert payload["applied_fixes"] == []


def test_status_search_validate_lint_smoke(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")
    # Ingest now drives normalize/chunk as part of the wiki generation pipeline,
    # so FTS/search material is already available.

    _, status = _invoke(["status"], workspace)
    assert status["status"] == "ok"
    assert status["summary"]["sources"] >= 1

    _, search = _invoke(["search", "pipeline"], workspace)
    assert search["status"] == "ok"
    assert isinstance(search["results"], list)
    # FTS picks up chunk text because "pipeline" appears in the short-note body.
    assert any(
        "pipeline" in json.dumps(item).lower() for item in search["results"]
    ), search

    _, validation = _invoke(["validate"], workspace)
    assert validation["status"] == "ok"
    assert validation["checks"]

    _, lint = _invoke(["lint"], workspace)
    assert lint["status"] == "ok"
    assert isinstance(lint["issues"], list)


def test_ask_uses_search_evidence_for_natural_language_query(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "rag.md")

    exit_code, ask = _invoke(["ask", "What does RAG combine?"], workspace)

    assert exit_code == 0
    assert ask["status"] == "ok"
    assert ask["answer"]
    assert ask["evidence_refs"]
    assert all("source_id" in ref for ref in ask["evidence_refs"])
    assert "vector" in ask["search_metadata"]
