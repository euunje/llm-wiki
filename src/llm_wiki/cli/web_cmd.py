from __future__ import annotations

import argparse

from llm_wiki.config import load_settings
from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def run_web_server(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - dependency guard
        return 1, {"status": "error", "message": f"uvicorn is required for wiki web: {exc}"}

    workspace = resolve_workspace(args.path)
    ensure_workspace(workspace)
    settings = load_settings(workspace.settings_file)
    web_settings = settings.get("web") or {}
    host = args.host or str(web_settings.get("host") or "")
    raw_port = args.port if args.port is not None else web_settings.get("port")

    from llm_wiki.web.app import create_app

    run_kwargs: dict[str, object] = {}
    if host:
        run_kwargs["host"] = host
    if raw_port not in (None, ""):
        run_kwargs["port"] = int(raw_port)

    uvicorn.run(create_app(workspace.root), **run_kwargs)
    return 0, {
        "status": "ok",
        "host": host or "uvicorn_default",
        "port": int(raw_port) if raw_port not in (None, "") else "uvicorn_default",
        "workspace": str(workspace.root),
        "message": "Web server stopped",
    }
