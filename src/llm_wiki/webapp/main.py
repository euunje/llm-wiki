"""FastAPI app factory for the LLM-Wiki web UI.

The app is bound to a single wiki project at creation time — the WikiPaths
are injected via `create_app()` so routes can access the current project
without re-resolving it on every request.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__
from .. import config as cfg


def _get_template_dir() -> Path:
    """Locate the webapp/templates directory packaged with llm_wiki."""
    return Path(__file__).parent / "templates"


def _get_static_dir() -> Path:
    """Locate the webapp/static directory packaged with llm_wiki."""
    return Path(__file__).parent / "static"


def create_app(paths: cfg.WikiPaths) -> FastAPI:
    """Build a FastAPI app bound to the given wiki project.

    Args:
        paths: Resolved wiki project paths. All routes will use these
               instead of re-walking the filesystem per request.

    Returns:
        A FastAPI application ready to be served with uvicorn.
    """
    app = FastAPI(
        title="LLM-Wiki",
        version=__version__,
        description="Local LLM-maintained personal wiki",
        docs_url=None,  # disable /docs in prod — this is a personal tool
        redoc_url=None,
    )

    # Stash the paths on the app state so routes can read it via request.app.state
    app.state.wiki_paths = paths
    app.state.version = __version__

    from fastapi.responses import RedirectResponse
    @app.middleware("http")
    async def check_setup_middleware(request: Request, call_next):
        path = request.url.path
        if not app.state.wiki_paths.is_initialized():
            if not path.startswith("/setup") and not path.startswith("/api/setup") and not path.startswith("/static") and not path.startswith("/guide"):
                return RedirectResponse(url="/setup")
        return await call_next(request)

    # Templates
    template_dir = _get_template_dir()
    templates = Jinja2Templates(directory=str(template_dir))
    app.state.templates = templates

    # Static files
    static_dir = _get_static_dir()
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Routes — import lazily to avoid circular dependencies
    from .routes import dashboard, graph, ingest, lint, query, sources, inbox, settings, mcp, setup, changelog

    app.include_router(dashboard.router)
    app.include_router(sources.router)
    app.include_router(graph.router)
    app.include_router(lint.router)
    app.include_router(query.router)
    app.include_router(ingest.router)
    app.include_router(inbox.router)
    app.include_router(settings.router)
    app.include_router(mcp.router)
    app.include_router(setup.router)
    app.include_router(changelog.router)

    return app


import os

def create_app_from_env() -> FastAPI:
    """Build a FastAPI app by resolving wiki path from WIKI_ROOT env variable."""
    wiki_root = os.environ.get("WIKI_ROOT")
    if not wiki_root:
        # Fallback to finding root or defaulting to current directory
        root = cfg.find_wiki_root() or Path.cwd()
        paths = cfg.WikiPaths(root=root)
    else:
        paths = cfg.WikiPaths(root=Path(wiki_root))

    if not paths.is_initialized():
        # Auto-scaffold if not initialized
        from ..scaffold import scaffold
        scaffold(paths.root)

    return create_app(paths)
