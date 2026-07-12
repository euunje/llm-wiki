"""Parser dispatcher — picks the right parser for a given file extension."""

from __future__ import annotations

from pathlib import Path

from .base import DocumentParser, ParsedDocument, ParserError
from .text import TextParser
from .pdf import PDFParser
from .docx import WordParser
from .html import HTMLParser
from .pptx import PowerpointParser

_PARSER_REGISTRY: list[DocumentParser] = [
    TextParser(),
    PDFParser(),
    WordParser(),
    HTMLParser(),
    PowerpointParser(),
]

SUPPORTED_EXTENSIONS = frozenset([
    ".md", ".markdown", ".txt", ".pdf", ".docx", ".html", ".htm", ".pptx"
])


def is_supported(path: Path) -> bool:
    """True if we have a parser for this file extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def parse(path: Path, chunk_size: int = 1500, overlap: int = 200) -> ParsedDocument:
    """Dispatch to the appropriate parser based on the file extension.

    Raises:
        ParserError: if the extension is unsupported or parsing fails.
    """
    if not path.exists():
        raise ParserError(f"File not found: {path}")
    if not path.is_file():
        raise ParserError(f"Not a regular file: {path}")

    ext = path.suffix.lower()
    for parser in _PARSER_REGISTRY:
        if parser.can_parse(ext):
            return parser.parse(path, chunk_size, overlap)

    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise ParserError(
        f"Unsupported file type '{ext}' for {path.name}. "
        f"Supported: {supported}"
    )


__all__ = ["ParsedDocument", "ParserError", "parse", "is_supported", "SUPPORTED_EXTENSIONS"]
