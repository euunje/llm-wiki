"""LLM Wiki Local — Web Review UI (Phase 3).

This package contains the FastAPI web application, Jinja2 templates,
and static assets for the local single-admin review interface.

Templates and static files are served by the FastAPI app defined in
`llm_wiki.web.app` (created by WU-002).
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

__all__ = ["PACKAGE_DIR", "TEMPLATES_DIR", "STATIC_DIR"]
