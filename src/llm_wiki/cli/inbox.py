from __future__ import annotations

import argparse
from pathlib import Path

from llm_wiki.config import load_settings
from llm_wiki.pipeline import scan_inbox
from llm_wiki.workspace import resolve_workspace


def run_inbox_scan(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    settings = load_settings(workspace.settings_file)
    configured = settings.get("inbox", {}).get("paths", {})
    if isinstance(configured, dict):
        configured_paths = list(configured.values())
    elif isinstance(configured, list):
        configured_paths = configured
    else:
        configured_paths = []
    scan_paths = [Path(args.scan_path).expanduser().resolve()] if args.scan_path else [workspace.root / path for path in configured_paths]
    payload = scan_inbox(workspace, scan_paths)
    payload.update({"workspace": str(workspace.root)})
    return 0, payload
