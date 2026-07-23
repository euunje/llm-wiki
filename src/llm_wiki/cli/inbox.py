from __future__ import annotations

import argparse
from pathlib import Path

from llm_wiki.config import load_settings
from llm_wiki.pipeline import scan_inbox
from llm_wiki.workspace import resolve_workspace


def _configured_scan_path(workspace_root: Path, raw_path: object) -> Path:
    path = Path(str(raw_path)).expanduser()
    if not path.is_absolute():
        path = workspace_root / path
    return path.resolve()


def _default_inbox_path(workspace_root: Path, settings: dict[str, object]) -> Path:
    inbox = settings.get("inbox") if isinstance(settings.get("inbox"), dict) else {}
    raw_path = (inbox or {}).get("path")
    if not raw_path:
        workspace_settings = settings.get("workspace") if isinstance(settings.get("workspace"), dict) else {}
        paths_settings = settings.get("paths") if isinstance(settings.get("paths"), dict) else {}
        vault_path = (workspace_settings or {}).get("human_vault") or (paths_settings or {}).get("vault") or "~/vault"
        raw_path = f"{str(vault_path).rstrip('/')}/00. Inbox"
    return _configured_scan_path(workspace_root, raw_path)


def run_inbox_scan(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    settings = load_settings(workspace.settings_file)
    scan_paths = [Path(args.scan_path).expanduser().resolve()] if args.scan_path else [_default_inbox_path(workspace.root, settings)]
    payload = scan_inbox(workspace, scan_paths)
    payload.update({"workspace": str(workspace.root)})
    return 0, payload
