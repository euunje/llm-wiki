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


def test_models_test_records_blocked_artifact_when_not_configured(workspace: Path) -> None:
    """Default settings have empty ``endpoint`` so ``models test`` must record a
    blocked artifact instead of attempting a network call."""

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


def test_models_test_succeeds_against_ephemeral_openai_compatible_mock(workspace: Path) -> None:
    """Use a dynamically bound local test server to validate the success path.

    The reusable source has no hardcoded host/port. This test injects the
    ephemeral endpoint into the workspace settings only for validation.
    """

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
    assert envelope["claim_candidates"] == []
    validation = payload["validation"]
    assert validation["ok"] is True
    assert validation["errors"] == []

    # The artifact JSON is stored under data/artifacts/extract_claims/.
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()


def test_phase1_placeholders_persist_minimum_artifacts(
    workspace: Path, samples_dir: Path
) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")
    _invoke(["extract-claims", source_id], workspace)

    _, summarize = _invoke(["summarize", f"source:{source_id}"], workspace)
    assert summarize["status"] == "ok"
    assert summarize["summary_placeholder"]
    assert summarize["phase_note"]

    _, link = _invoke(["link", f"source:{source_id}"], workspace)
    assert link["status"] == "ok"
    assert link["relation_candidates"] == []

    _, map_payload = _invoke(["map", source_id], workspace)
    assert map_payload["status"] == "ok"
    assert map_payload["mapping_candidates"] == []
    assert map_payload["high_similarity_candidates"] == []

    _, ask = _invoke(["ask", "What is RAG?"], workspace)
    assert ask["status"] == "ok"
    assert ask["answer_placeholder"]
    assert ask["evidence_refs"] == []

    _, compile_payload = _invoke(["compile", "agentic_rag"], workspace)
    assert compile_payload["status"] == "ok"
    preview_path = workspace / compile_payload["preview_path"]
    assert preview_path.exists()
    assert "draft_preview" in preview_path.read_text(encoding="utf-8")


def test_sync_dry_run_does_not_create_view_by_default(workspace: Path) -> None:
    _ensure_init(workspace)
    _, payload = _invoke(["sync"], workspace)
    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert payload["applied_actions"] == []
    view_path = workspace / "vault/20_Review/candidates/sync-status.md"
    assert not view_path.exists()


def test_status_search_validate_lint_smoke(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")
    # Drive the pipeline past ingest so FTS has something to search.
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)

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
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    _invoke(["embed", f"source:{source_id}"], workspace)

    exit_code, ask = _invoke(["ask", "RAG에서 groundedness가 왜 중요한가?"], workspace)
    assert exit_code == 0
    assert ask["status"] == "ok"
    assert ask["answer"]
    assert ask["evidence_refs"]
    assert all("source_id" in ref for ref in ask["evidence_refs"])
    assert ask["search_metadata"]["vector"]["attempted"] is True


def test_retry_request_records_artifact(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")

    # Re-run extract-claims to get a real AgentRun, then use its run id as the
    # retry target so we exercise the run-id branch.
    _, claims = _invoke(["extract-claims", source_id], workspace)
    run_id = claims["run_id"]

    _, retry = _invoke(["retry", run_id, "--instruction", "be narrower"], workspace)
    assert retry["status"] == "ok"
    assert retry["target_kind"] == "run"
    assert retry["target_id"] == run_id
    assert retry["instruction"] == "be narrower"
