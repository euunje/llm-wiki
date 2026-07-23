from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from llm_wiki.cli.chunk_cmd import run_chunk
from llm_wiki.cli.doctor import run_doctor
from llm_wiki.cli.embed_cmd import run_embed
from llm_wiki.cli.init_cmd import run_init
from llm_wiki.cli.ingest import run_ingest, run_ingest_text
from llm_wiki.cli.inbox import run_inbox_scan
from llm_wiki.cli.models_cmd import run_models_list, run_models_test
from llm_wiki.cli.normalize_cmd import run_normalize
from llm_wiki.cli.ops_cmds import (
    run_fix,
    run_healthcheck,
    run_lint,
    run_search,
    run_status,
    run_validate,
)
from llm_wiki.cli.phase1_placeholders import run_ask, run_extract_claims
from llm_wiki.cli.route_cmd import run_route_get, run_route_set
from llm_wiki.cli.settings_cmd import run_settings_get, run_settings_set
from llm_wiki.cli.web_cmd import run_web_server
from llm_wiki.config import SettingsError
from llm_wiki.pipeline import UnsupportedInputError, UserInputError


ExitHandler = Callable[[argparse.Namespace], tuple[int, dict[str, Any]]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wiki", description="LLM Wiki Local CLI")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize workspace folders, settings, and database")
    init_parser.add_argument("--path", default=".", help="Workspace root path")
    init_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    init_parser.set_defaults(handler=run_init)

    settings_parser = subparsers.add_parser("settings", help="Get or set workspace settings")
    settings_subparsers = settings_parser.add_subparsers(dest="settings_command")

    settings_get = settings_subparsers.add_parser("get", help="Read settings")
    settings_get.add_argument("key", nargs="?", help="Optional dotted settings key")
    settings_get.add_argument("--path", default=".", help="Workspace root path")
    settings_get.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    settings_get.set_defaults(handler=run_settings_get)

    settings_set = settings_subparsers.add_parser("set", help="Update settings")
    settings_set.add_argument("key", help="Dotted settings key")
    settings_set.add_argument("value", help="New value")
    settings_set.add_argument("--path", default=".", help="Workspace root path")
    settings_set.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    settings_set.set_defaults(handler=run_settings_set)

    doctor_parser = subparsers.add_parser("doctor", help="Check local workspace health")
    doctor_parser.add_argument("--path", default=".", help="Workspace root path")
    doctor_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    doctor_parser.set_defaults(handler=run_doctor)

    inbox_parser = subparsers.add_parser("inbox", help="Inbox operations")
    inbox_subparsers = inbox_parser.add_subparsers(dest="inbox_command")
    inbox_scan = inbox_subparsers.add_parser("scan", help="Scan inbox paths for Markdown sources")
    inbox_scan.add_argument("scan_path", nargs="?", help="Optional inbox directory or Markdown file path")
    inbox_scan.add_argument("--path", default=".", help="Workspace root path")
    inbox_scan.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    inbox_scan.set_defaults(handler=run_inbox_scan)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a Markdown file")
    ingest_parser.add_argument("input_path", help="Markdown file path")
    ingest_parser.add_argument("--llm", action="store_true", dest="use_llm", help="Attempt LLM-assisted extraction with deterministic fallback")
    ingest_parser.add_argument("--path", default=".", help="Workspace root path")
    ingest_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    ingest_parser.set_defaults(handler=run_ingest)

    ingest_text_parser = subparsers.add_parser("ingest-text", help="Ingest raw text as a source")
    ingest_text_parser.add_argument("title", help="Source title")
    ingest_text_parser.add_argument("--text", help="Source text; if omitted, stdin is used when piped")
    ingest_text_parser.add_argument("--path", default=".", help="Workspace root path")
    ingest_text_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    ingest_text_parser.set_defaults(handler=run_ingest_text)

    normalize_parser = subparsers.add_parser("normalize", help="Normalize a source into Markdown")
    normalize_parser.add_argument("source_id", help="Source ID")
    normalize_parser.add_argument("--path", default=".", help="Workspace root path")
    normalize_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    normalize_parser.set_defaults(handler=run_normalize)

    chunk_parser = subparsers.add_parser("chunk", help="Chunk a normalized source")
    chunk_parser.add_argument("source_id", help="Source ID")
    chunk_parser.add_argument("--path", default=".", help="Workspace root path")
    chunk_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    chunk_parser.set_defaults(handler=run_chunk)

    embed_parser = subparsers.add_parser("embed", help="Embed chunk targets")
    embed_parser.add_argument("target", help="Target selector such as source:<id>, chunk:<id>, or all")
    embed_parser.add_argument("--path", default=".", help="Workspace root path")
    embed_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    embed_parser.set_defaults(handler=run_embed)

    models_parser = subparsers.add_parser("models", help="LLM model operations")
    models_subparsers = models_parser.add_subparsers(dest="models_command")
    models_list = models_subparsers.add_parser("list", help="List configured models")
    models_list.add_argument("--path", default=".", help="Workspace root path")
    models_list.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    models_list.set_defaults(handler=run_models_list)
    models_test = models_subparsers.add_parser("test", help="Test a configured model endpoint")
    models_test.add_argument("model_id", help="Configured model ID")
    models_test.add_argument("--path", default=".", help="Workspace root path")
    models_test.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    models_test.set_defaults(handler=run_models_test)

    route_parser = subparsers.add_parser("route", help="Task routing operations")
    route_subparsers = route_parser.add_subparsers(dest="route_command")
    route_get = route_subparsers.add_parser("get", help="Get route mapping")
    route_get.add_argument("task_type", nargs="?", help="Optional task type")
    route_get.add_argument("--path", default=".", help="Workspace root path")
    route_get.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    route_get.set_defaults(handler=run_route_get)
    route_set = route_subparsers.add_parser("set", help="Set route mapping")
    route_set.add_argument("task_type", help="Task type")
    route_set.add_argument("model_id", help="Model ID")
    route_set.add_argument("--path", default=".", help="Workspace root path")
    route_set.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    route_set.set_defaults(handler=run_route_set)

    extract_claims = subparsers.add_parser("extract-claims", help="Phase 1 extract-claims candidate contract")
    extract_claims.add_argument("source_id", help="Source ID")
    extract_claims.add_argument("--llm", action="store_true", dest="use_llm", help="Use configured chat model for Phase 2 JSON extraction")
    extract_claims.add_argument("--path", default=".", help="Workspace root path")
    extract_claims.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    extract_claims.set_defaults(handler=run_extract_claims)

    ask_parser = subparsers.add_parser("ask", help="Ask a question against the workspace search/RAG index")
    ask_parser.add_argument("query", help="Question text")
    ask_parser.add_argument("--path", default=".", help="Workspace root path")
    ask_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    ask_parser.set_defaults(handler=run_ask)

    validate_parser = subparsers.add_parser("validate", help="Minimal Phase 1 validation report")
    validate_parser.add_argument("target", nargs="?", help="Optional target or artifact path")
    validate_parser.add_argument("--path", default=".", help="Workspace root path")
    validate_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    validate_parser.set_defaults(handler=run_validate)

    lint_parser = subparsers.add_parser("lint", help="Minimal Phase 1 lint report")
    lint_parser.add_argument("target", nargs="?", help="Optional target")
    lint_parser.add_argument("--path", default=".", help="Workspace root path")
    lint_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    lint_parser.set_defaults(handler=run_lint)

    repair_parser = subparsers.add_parser(
        "debug-repair-source-stubs",
        help="Debug: repair missing source stub markdown files",
    )
    repair_parser.add_argument("target", nargs="?", help="Optional target")
    repair_parser.add_argument("--apply", action="store_true", help="Apply safe source-stub repairs")
    repair_parser.add_argument("--path", default=".", help="Workspace root path")
    repair_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    repair_parser.set_defaults(handler=run_fix)

    status_parser = subparsers.add_parser("status", help="Workspace status summary")
    status_parser.add_argument("--path", default=".", help="Workspace root path")
    status_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    status_parser.set_defaults(handler=run_status)

    search_parser = subparsers.add_parser("search", help="Phase 1 FTS/metadata search")
    search_parser.add_argument("query", nargs="?", help="Search query")
    search_parser.add_argument("--path", default=".", help="Workspace root path")
    search_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    search_parser.set_defaults(handler=run_search)

    healthcheck_parser = subparsers.add_parser("healthcheck", help="Minimal data healthcheck report")
    healthcheck_parser.add_argument("--path", default=".", help="Workspace root path")
    healthcheck_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output")
    healthcheck_parser.set_defaults(handler=run_healthcheck)

    web_parser = subparsers.add_parser("web", help="Run the local FastAPI web review UI")
    web_parser.add_argument("--path", default=".", help="Workspace root path")
    web_parser.add_argument("--host", help="Bind host; defaults to settings.web.host")
    web_parser.add_argument("--port", type=int, help="Bind port; defaults to settings.web.port")
    web_parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON output after shutdown")
    web_parser.set_defaults(handler=run_web_server)

    return parser


def emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return
    if "message" in payload:
        print(payload["message"])
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: ExitHandler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        exit_code, payload = handler(args)
    except (ValueError, SettingsError, UserInputError, UnsupportedInputError) as exc:
        emit({"status": "error", "message": str(exc)}, getattr(args, "json_output", False))
        return 2
    except Exception as exc:  # pragma: no cover - top-level safeguard
        emit({"status": "error", "message": str(exc)}, getattr(args, "json_output", False))
        return 1
    emit(payload, getattr(args, "json_output", False))
    return exit_code
