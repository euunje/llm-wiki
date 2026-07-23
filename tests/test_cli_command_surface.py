from __future__ import annotations

from llm_wiki.cli import build_parser


def _top_level_commands() -> set[str]:
    parser = build_parser()
    subparsers = next(action for action in parser._actions if getattr(action, "dest", None) == "command")
    return set(subparsers.choices)


def test_cli_command_surface_groups_debug_repair_and_removes_obsolete_commands() -> None:
    commands = _top_level_commands()

    assert "debug-repair-source-stubs" in commands
    assert "fix" not in commands
    assert "sync" not in commands
    assert "retry" not in commands


def test_cli_keeps_operational_and_debug_commands() -> None:
    commands = _top_level_commands()

    assert {
        "init",
        "ingest",
        "ingest-text",
        "inbox",
        "ask",
        "search",
        "status",
        "web",
        "settings",
        "models",
        "route",
        "doctor",
        "healthcheck",
        "normalize",
        "chunk",
        "embed",
        "extract-claims",
        "validate",
        "lint",
    } <= commands
