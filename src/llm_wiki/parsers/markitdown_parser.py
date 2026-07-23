"""Parser backed by Microsoft MarkItDown.

MarkItDown converts office/doc-like inputs to Markdown. This parser is the
primary ingestion path for rich documents; format-specific local parsers remain
available as fallbacks from the dispatcher.
"""

from __future__ import annotations

from pathlib import Path

from .base import ParsedDocument, ParserError, compute_hash, fallback_title_from_path, normalize_text

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
}


def _first_heading_or_line(text: str) -> str | None:
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("#"):
            clean = clean.lstrip("#").strip()
        if clean and len(clean) <= 200:
            return clean
    return None


def parse(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ParserError(f"MarkItDown parser does not support '{suffix}'")
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise ParserError("markitdown is not installed. Run `uv pip install -e .`.") from e

    try:
        result = MarkItDown(enable_plugins=False).convert(path)
    except Exception as e:
        raise ParserError(f"MarkItDown failed for {path.name}: {e}") from e

    markdown = getattr(result, "markdown", None) or getattr(result, "text_content", None) or ""
    text = normalize_text(str(markdown))
    title = _first_heading_or_line(text) or fallback_title_from_path(path)
    file_type = suffix.lstrip(".")
    if file_type == "htm":
        file_type = "html"
    metadata = {
        "converter": "markitdown",
        "suffix": suffix,
    }
    return ParsedDocument(
        source_path=path,
        file_type=file_type,
        title=title,
        text=text,
        content_hash=compute_hash(text),
        bytes=path.stat().st_size,
        metadata=metadata,
    )
