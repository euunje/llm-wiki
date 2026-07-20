from __future__ import annotations

import argparse

from llm_wiki.llm import get_route_map, set_route_model
from llm_wiki.workspace import resolve_workspace


def run_route_get(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = get_route_map(workspace, args.task_type)
    payload["workspace"] = str(workspace.root)
    return 0, payload


def run_route_set(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = set_route_model(workspace, args.task_type, args.model_id)
    payload["workspace"] = str(workspace.root)
    return 0, payload
