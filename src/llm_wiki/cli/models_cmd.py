from __future__ import annotations

import argparse

from llm_wiki.llm import list_models, test_model_connection
from llm_wiki.workspace import resolve_workspace


def run_models_list(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = list_models(workspace)
    payload["workspace"] = str(workspace.root)
    return 0, payload


def run_models_test(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    exit_code, payload = test_model_connection(workspace, args.model_id)
    payload["workspace"] = str(workspace.root)
    return exit_code, payload
