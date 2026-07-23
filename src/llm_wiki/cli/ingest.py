from __future__ import annotations

import argparse
import sys

from llm_wiki.pipeline import ingest_markdown_file, ingest_text
from llm_wiki.workspace import resolve_workspace


def run_ingest(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    payload = ingest_markdown_file(workspace, args.input_path, use_llm=getattr(args, "use_llm", False))
    payload.update({"workspace": str(workspace.root)})
    return 0 if payload.get("status") != "duplicate" else 0, payload


def run_ingest_text(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    text = args.text
    origin = "argument"
    if text is None and not sys.stdin.isatty():
        text = sys.stdin.read()
        origin = "stdin"
    if text is None:
        raise ValueError("Provide --text or pipe text on stdin")
    payload = ingest_text(workspace, args.title, text, origin=origin)
    payload.update({"workspace": str(workspace.root)})
    return 0 if payload.get("status") != "duplicate" else 0, payload
