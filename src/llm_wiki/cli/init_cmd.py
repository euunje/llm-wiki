from __future__ import annotations

import argparse

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def run_init(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    result = ensure_workspace(workspace)
    payload = {
        "status": "ok",
        "workspace": str(workspace.root),
        "db_path": str(workspace.db),
        "settings_path": str(workspace.settings_file),
        **result,
        "message": f"Initialized workspace at {workspace.root}",
    }
    return 0, payload
