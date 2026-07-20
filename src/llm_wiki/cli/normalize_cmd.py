from __future__ import annotations

import argparse

from llm_wiki.pipeline import normalize_source
from llm_wiki.workspace import resolve_workspace


def run_normalize(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = normalize_source(workspace, args.source_id)
    payload.update({"workspace": str(workspace.root)})
    return 0, payload
