"""Parser dispatcher — picks the right parser for a given file extension."""

from __future__ import annotations

from pathlib import Path

from .base import ParsedDocument, ParserError

# Map lowercase extension → module path of the parser
_PARSERS = {
    ".md": "text",
    ".markdown": "text",
    ".txt": "text",
    ".pdf": "markitdown",
    ".docx": "markitdown",
    ".pptx": "markitdown",
    ".xlsx": "markitdown",
    ".xls": "markitdown",
    ".html": "markitdown",
    ".htm": "markitdown",
}

_FALLBACK_PARSERS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
}

SUPPORTED_EXTENSIONS = frozenset(_PARSERS.keys())


def is_supported(path: Path) -> bool:
    """True if we have a parser for this file extension."""
    return path.suffix.lower() in _PARSERS


def _load_parser_module(module_name: str):
    if module_name == "text":
        from . import text as parser_module
    elif module_name == "markitdown":
        from . import markitdown_parser as parser_module
    elif module_name == "pdf":
        from . import pdf as parser_module
    elif module_name == "docx":
        from . import docx as parser_module
    elif module_name == "html":
        from . import html as parser_module
    else:
        raise ParserError(f"Internal error: unknown parser '{module_name}'")
    return parser_module


def parse(path: Path) -> ParsedDocument:
    """Dispatch to the appropriate parser based on the file extension.

    Raises:
        ParserError: if the extension is unsupported or parsing fails.
    """
    if not path.exists():
        raise ParserError(f"File not found: {path}")
    if not path.is_file():
        raise ParserError(f"Not a regular file: {path}")

    ext = path.suffix.lower()
    if ext not in _PARSERS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ParserError(
            f"Unsupported file type '{ext}' for {path.name}. "
            f"Supported: {supported}"
        )

    module_name = _PARSERS[ext]
    parser_module = _load_parser_module(module_name)
    try:
        return parser_module.parse(path)
    except ParserError:
        fallback_module_name = _FALLBACK_PARSERS.get(ext)
        if not fallback_module_name or fallback_module_name == module_name:
            raise
        fallback_module = _load_parser_module(fallback_module_name)
        return fallback_module.parse(path)


__all__ = ["ParsedDocument", "ParserError", "parse", "is_supported", "SUPPORTED_EXTENSIONS"]
