"""Phase 2 non-Markdown converter adapter.

This module provides a converter adapter API for converting non-Markdown inputs
(HTML, PDF, Office, URL) to normalized Markdown for pipeline processing.

Architecture:
- ConverterAdapter: Abstract base defining the conversion interface
- MarkdownPassThroughAdapter: Pass-through for actual Markdown files
- HtmlToMarkdownAdapter: HTML -> Markdown using stdlib html.parser
- UnsupportedAdapter: Returns explicit failure artifact for PDF/Office/URL
  when optional dependency is unavailable

No mandatory external dependencies are added. PDF/Office support would
require optional dependencies (e.g., markitdown) in Phase 3+.

Phase 2 guidance:
- HTML: Basic extraction via stdlib, converted to normalized Markdown
- PDF: Explicit UnsupportedInputError with Phase 2 conversion guidance
- Office: Explicit UnsupportedInputError with Phase 2 conversion guidance
- URL: Explicit UnsupportedInputError (Phase 2 does not add URL support)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from llm_wiki.pipeline.errors import UnsupportedInputError


# Guidance messages for unsupported types
_UNSUPPORTED_GUIDANCE = {
    ".pdf": (
        "PDF input requires Phase 2+ conversion support. "
        "Install optional dependency (e.g., markitdown) or convert to Markdown manually."
    ),
    ".doc": (
        "Office .doc input requires Phase 2+ conversion support. "
        "Convert to .docx or Markdown manually."
    ),
    ".docx": (
        "Office .docx input requires Phase 2+ conversion support. "
        "Convert to Markdown manually or use optional conversion tool."
    ),
    ".ppt": (
        "Office .ppt input requires Phase 2+ conversion support. "
        "Convert to .pptx or Markdown manually."
    ),
    ".pptx": (
        "Office .pptx input requires Phase 2+ conversion support. "
        "Convert to Markdown manually or use optional conversion tool."
    ),
    ".xls": (
        "Office .xls input requires Phase 2+ conversion support. "
        "Convert to .xlsx or CSV manually."
    ),
    ".xlsx": (
        "Office .xlsx input requires Phase 2+ conversion support. "
        "Convert to CSV or Markdown manually or use optional conversion tool."
    ),
    ".url": (
        "URL input is not supported in Phase 2. "
        "Phase 3 will add URL-to-Markdown conversion."
    ),
}


@dataclass
class ConversionResult:
    """Result of a conversion attempt."""

    success: bool
    converted_text: str | None = None
    error_message: str | None = None
    artifact_payload: dict[str, Any] | None = None
    source_type: str | None = None  # e.g., "html", "converted_markdown"


class ConverterAdapter(ABC):
    """Abstract base class for converter adapters."""

    @abstractmethod
    def can_convert(self, path: Path) -> bool:
        """Check if this adapter can handle the given file."""
        pass

    @abstractmethod
    def convert(self, path: Path) -> ConversionResult:
        """Convert the file to normalized Markdown.

        Returns:
            ConversionResult with success=True and converted_text if successful.
            If conversion fails, returns success=False with error_message and
            artifact_payload for error artifact recording.
        """
        pass


class MarkdownPassThroughAdapter(ConverterAdapter):
    """Pass-through adapter for actual Markdown files."""

    MARKDOWN_SUFFIXES = {".md", ".markdown"}

    def can_convert(self, path: Path) -> bool:
        return path.suffix.lower() in self.MARKDOWN_SUFFIXES

    def convert(self, path: Path) -> ConversionResult:
        try:
            text = path.read_text(encoding="utf-8")
            return ConversionResult(
                success=True,
                converted_text=text,
                source_type="markdown_file",
            )
        except Exception as exc:  # pragma: no cover - file read errors
            return ConversionResult(
                success=False,
                error_message=f"Failed to read Markdown file: {exc}",
                artifact_payload={
                    "status": "error",
                    "reason": str(exc),
                    "type": "markdown_read_error",
                    "path": str(path),
                },
                source_type="markdown_file",
            )


class _HtmlToMarkdownConverter(HTMLParser):
    """HTML to Markdown converter using stdlib HTMLParser.

    Extracts text content and converts basic HTML elements to Markdown format.
    This is a best-effort conversion using only stdlib.
    """

    def __init__(self) -> None:
        super().__init__()
        self._result: list[str] = []
        self._in_pre = False
        self._in_title = False
        self._title_text: str | None = None
        self._link_stack: list[tuple[str, str]] = []  # (href, text) pairs for nested links

    def _append(self, text: str) -> None:
        if self._result and self._result[-1] and not self._result[-1].endswith("\n"):
            if text:
                self._result[-1] += text
        else:
            self._result.append(text)

    def _flush_line(self) -> None:
        """Ensure current line ends with newline."""
        if self._result and self._result[-1] and not self._result[-1].endswith("\n"):
            self._result[-1] += "\n"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "h1":
            self._flush_line()
            self._append("# ")
        elif tag == "h2":
            self._flush_line()
            self._append("## ")
        elif tag == "h3":
            self._flush_line()
            self._append("### ")
        elif tag == "h4":
            self._flush_line()
            self._append("#### ")
        elif tag == "h5":
            self._flush_line()
            self._append("##### ")
        elif tag == "h6":
            self._flush_line()
            self._append("###### ")
        elif tag == "p":
            self._flush_line()
        elif tag == "br":
            self._append("\n")
        elif tag == "pre":
            self._flush_line()
            self._append("```\n")
            self._in_pre = True
        elif tag == "code":
            if not self._in_pre:
                self._append("`")
        elif tag == "strong" or tag == "b":
            self._append("**")
        elif tag == "em" or tag == "i":
            self._append("*")
        elif tag == "a":
            href = attrs_dict.get("href", "")
            title = attrs_dict.get("title", "")
            self._link_stack.append((href, title))
            self._append("[")
        elif tag == "ul":
            self._flush_line()
        elif tag == "ol":
            self._flush_line()
        elif tag == "li":
            # Check if inside ol by looking at parent context (simplified)
            self._append("- ")
        elif tag == "blockquote":
            self._flush_line()
            self._append("> ")
        elif tag == "hr":
            self._flush_line()
            self._append("---\n")
        elif tag == "img":
            alt = attrs_dict.get("alt", "")
            src = attrs_dict.get("src", "")
            self._append(f"![{alt}]({src})")
        elif tag == "title":
            self._in_title = True
            self._title_text = None

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" or tag == "h2" or tag == "h3" or tag == "h4" or tag == "h5" or tag == "h6":
            self._flush_line()
        elif tag == "p":
            self._flush_line()
        elif tag == "pre":
            self._append("\n```\n")
            self._in_pre = False
        elif tag == "code":
            if not self._in_pre:
                self._append("`")
        elif tag == "strong" or tag == "b":
            self._append("**")
        elif tag == "em" or tag == "i":
            self._append("*")
        elif tag == "a":
            if self._link_stack:
                href, title = self._link_stack.pop()
                if title:
                    self._append(f"]({href} \"{title}\")")
                else:
                    self._append(f"]({href})")
        elif tag == "ul" or tag == "ol":
            self._flush_line()
        elif tag == "li":
            self._flush_line()
        elif tag == "blockquote":
            self._flush_line()
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            if self._title_text is None:
                self._title_text = data
            else:
                self._title_text += data
        if self._in_pre:
            self._result.append(data)
        else:
            # Normalize whitespace
            cleaned = re.sub(r"[ \t]+", " ", data)
            cleaned = cleaned.replace("\n", " ").strip()
            if cleaned:
                self._append(cleaned)

    def handle_comment(self, data: str) -> None:
        # Skip HTML comments
        pass

    def handle_decl(self, decl: str) -> None:
        # Skip DOCTYPE declarations
        pass

    @property
    def title(self) -> str | None:
        return self._title_text

    def to_markdown(self) -> str:
        """Convert accumulated HTML to Markdown text."""
        if not self._result:
            return ""
        # Join and normalize multiple newlines
        result = "\n".join(self._result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip() + "\n"


class HtmlToMarkdownAdapter(ConverterAdapter):
    """HTML to Markdown adapter using stdlib only.

    Converts HTML files to normalized Markdown using html.parser.
    Best-effort conversion - not all HTML features are supported.
    """

    HTML_SUFFIXES = {".html", ".htm"}

    def can_convert(self, path: Path) -> bool:
        return path.suffix.lower() in self.HTML_SUFFIXES

    def convert(self, path: Path) -> ConversionResult:
        try:
            html_content = path.read_text(encoding="utf-8")
        except Exception as exc:
            return ConversionResult(
                success=False,
                error_message=f"Failed to read HTML file: {exc}",
                artifact_payload={
                    "status": "error",
                    "reason": str(exc),
                    "type": "html_read_error",
                    "path": str(path),
                },
                source_type="html",
            )

        try:
            parser = _HtmlToMarkdownConverter()
            parser.feed(html_content)
            markdown_text = parser.to_markdown()
            title = parser.title
            if title:
                markdown_text = f"# {title}\n\n{markdown_text}"
            return ConversionResult(
                success=True,
                converted_text=markdown_text,
                source_type="converted_markdown",
            )
        except Exception as exc:
            return ConversionResult(
                success=False,
                error_message=f"HTML parsing failed: {exc}",
                artifact_payload={
                    "status": "error",
                    "reason": str(exc),
                    "type": "html_parse_error",
                    "path": str(path),
                },
                source_type="html",
            )


class UnsupportedAdapter(ConverterAdapter):
    """Adapter for unsupported file types.

    Returns explicit failure result with Phase 2 guidance for PDF/Office/URL.
    This ensures non-Markdown files no longer silently claim success.
    """

    UNSUPPORTED_SUFFIXES = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
    }

    def can_convert(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        path_str = str(path)
        # Also handle URLs (Path converts https:// to https:/ so check both forms)
        if path_str.startswith(("http://", "https://")) or path_str.startswith(("http:/", "https:/")):
            return True
        return suffix in self.UNSUPPORTED_SUFFIXES

    def convert(self, path: Path) -> ConversionResult:
        suffix = path.suffix.lower()
        path_str = str(path)
        # Path converts https:// to https:/ so check both forms
        if path_str.startswith(("http://", "https://")) or path_str.startswith(("http:/", "https:/")):
            guidance = _UNSUPPORTED_GUIDANCE.get(".url", "URL input requires Phase 2+ conversion support.")
            return ConversionResult(
                success=False,
                error_message=f"URL input is unsupported: {guidance}",
                artifact_payload={
                    "status": "error",
                    "reason": guidance,
                    "type": "url_unsupported",
                    "url": str(path),
                    "phase": "phase2",
                },
                source_type="url",
            )
        guidance = _UNSUPPORTED_GUIDANCE.get(suffix, f"Unsupported input type '{suffix}' in Phase 2.")
        return ConversionResult(
            success=False,
            error_message=f"Unsupported input type '{suffix}': {guidance}",
            artifact_payload={
                "status": "error",
                "reason": guidance,
                "type": "unsupported_conversion",
                "suffix": suffix,
                "path": str(path),
                "phase": "phase2",
            },
            source_type=suffix.lstrip("."),
        )


class ConverterAdapterRegistry:
    """Registry for converter adapters.

    Tries adapters in order and returns first successful conversion
    or final failure result.
    """

    def __init__(self) -> None:
        self._adapters: list[ConverterAdapter] = [
            MarkdownPassThroughAdapter(),
            HtmlToMarkdownAdapter(),
            UnsupportedAdapter(),
        ]

    def convert(self, path: Path) -> ConversionResult:
        """Attempt conversion using registered adapters.

        Tries MarkdownPassThrough first, then HtmlToMarkdown, then UnsupportedAdapter.
        Returns first successful conversion or final failure from UnsupportedAdapter.
        """
        for adapter in self._adapters:
            if adapter.can_convert(path):
                result = adapter.convert(path)
                if result.success:
                    return result
                # For UnsupportedAdapter, return its failure result
                if isinstance(adapter, UnsupportedAdapter):
                    return result
                # For other adapters, continue to next adapter on failure
        # Fallback: should not reach here, but return error if it does
        return ConversionResult(
            success=False,
            error_message=f"No converter available for: {path}",
            artifact_payload={
                "status": "error",
                "reason": f"No converter available for: {path}",
                "type": "no_converter",
                "path": str(path),
            },
        )


# Module-level singleton registry instance
_registry: ConverterAdapterRegistry | None = None


def get_converter_registry() -> ConverterAdapterRegistry:
    """Get the module-level converter registry instance."""
    global _registry
    if _registry is None:
        _registry = ConverterAdapterRegistry()
    return _registry


def convert_input(path: Path) -> ConversionResult:
    """Convenience function to convert any supported input to Markdown.

    Uses the global converter registry to attempt conversion.

    Args:
        path: Path to the input file

    Returns:
        ConversionResult with converted text or error with artifact payload
    """
    return get_converter_registry().convert(path)
