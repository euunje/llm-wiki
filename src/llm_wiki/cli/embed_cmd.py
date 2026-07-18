from __future__ import annotations

import argparse

from llm_wiki.pipeline import embed_target
from llm_wiki.workspace import resolve_workspace


def run_embed(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = embed_target(workspace, args.target)
    payload.update({"workspace": str(workspace.root)})
    return 0, payload
