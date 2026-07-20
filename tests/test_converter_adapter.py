"""Phase 2 converter adapter tests.

Tests for:
- HTML conversion success
- PDF dependency-missing failure (explicit error artifact)
- Markdown pass-through unchanged
- Existing Markdown ingest behavior unchanged
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.pipeline import UnsupportedInputError
from llm_wiki.pipeline.convert import (
    ConversionResult,
    ConverterAdapterRegistry,
    HtmlToMarkdownAdapter,
    MarkdownPassThroughAdapter,
    UnsupportedAdapter,
    convert_input,
)
from llm_wiki.pipeline.hashing import UNSUPPORTED_SUFFIX_GUIDANCE


class TestHtmlToMarkdownAdapter:
    """Tests for HTML to Markdown conversion using stdlib."""

    def test_can_convert_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")
        adapter = HtmlToMarkdownAdapter()
        assert adapter.can_convert(html_file) is True

    def test_can_convert_htm(self, tmp_path: Path) -> None:
        htm_file = tmp_path / "test.htm"
        htm_file.write_text("<html></html>")
        adapter = HtmlToMarkdownAdapter()
        assert adapter.can_convert(htm_file) is True

    def test_cannot_convert_md(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello")
        adapter = HtmlToMarkdownAdapter()
        assert adapter.can_convert(md_file) is False

    def test_cannot_convert_pdf(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        adapter = HtmlToMarkdownAdapter()
        assert adapter.can_convert(pdf_file) is False

    def test_convert_simple_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><h1>Hello World</h1><p>This is a test.</p></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "# Hello World" in result.converted_text
        assert "This is a test" in result.converted_text
        assert result.source_type == "converted_markdown"

    def test_convert_html_with_links(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text('<html><body><p>Visit <a href="https://example.com">Example</a>.</p></body></html>')

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "[Example](https://example.com)" in result.converted_text

    def test_convert_html_with_code(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><p>Use <code>print('hello')</code> for output.</p></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "`print('hello')`" in result.converted_text

    def test_convert_html_with_strong_em(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><p><strong>Bold</strong> and <em>italic</em>.</p></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "**Bold**" in result.converted_text
        assert "*italic*" in result.converted_text

    def test_convert_html_with_list(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><ul><li>Item 1</li><li>Item 2</li></ul></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "- Item 1" in result.converted_text
        assert "- Item 2" in result.converted_text

    def test_convert_html_with_blockquote(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><blockquote>This is a quote.</blockquote></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "> This is a quote" in result.converted_text

    def test_convert_html_with_title(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><head><title>Page Title</title></head><body><p>Content</p></body></html>")

        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is True
        assert result.converted_text is not None
        assert "# Page Title" in result.converted_text
        assert "Content" in result.converted_text

    def test_convert_html_read_error(self, tmp_path: Path) -> None:
        # File doesn't exist
        html_file = tmp_path / "nonexistent.html"
        adapter = HtmlToMarkdownAdapter()
        result = adapter.convert(html_file)

        assert result.success is False
        assert result.error_message is not None
        assert "Failed to read HTML file" in result.error_message
        assert result.artifact_payload is not None
        assert result.artifact_payload["type"] == "html_read_error"


class TestMarkdownPassThroughAdapter:
    """Tests for Markdown pass-through adapter."""

    def test_can_convert_md(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello")
        adapter = MarkdownPassThroughAdapter()
        assert adapter.can_convert(md_file) is True

    def test_can_convert_markdown(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.markdown"
        md_file.write_text("# Hello")
        adapter = MarkdownPassThroughAdapter()
        assert adapter.can_convert(md_file) is True

    def test_cannot_convert_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")
        adapter = MarkdownPassThroughAdapter()
        assert adapter.can_convert(html_file) is False

    def test_convert_markdown_passthrough(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        content = "# Hello World\n\nThis is a test."
        md_file.write_text(content)

        adapter = MarkdownPassThroughAdapter()
        result = adapter.convert(md_file)

        assert result.success is True
        assert result.converted_text == content
        assert result.source_type == "markdown_file"


class TestUnsupportedAdapter:
    """Tests for unsupported file type handling."""

    def test_can_convert_pdf(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        adapter = UnsupportedAdapter()
        assert adapter.can_convert(pdf_file) is True

    def test_can_convert_docx(self, tmp_path: Path) -> None:
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK fake docx")
        adapter = UnsupportedAdapter()
        assert adapter.can_convert(docx_file) is True

    def test_cannot_convert_md(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello")
        adapter = UnsupportedAdapter()
        assert adapter.can_convert(md_file) is False

    def test_cannot_convert_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html></html>")
        adapter = UnsupportedAdapter()
        assert adapter.can_convert(html_file) is False

    def test_convert_pdf_returns_error_with_phase2_guidance(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        adapter = UnsupportedAdapter()
        result = adapter.convert(pdf_file)

        assert result.success is False
        assert result.error_message is not None
        assert "Phase 2" in result.error_message or "Phase 2+" in result.error_message
        assert result.artifact_payload is not None
        assert result.artifact_payload["type"] == "unsupported_conversion"
        assert result.artifact_payload["suffix"] == ".pdf"
        assert result.artifact_payload["phase"] == "phase2"

    def test_convert_docx_returns_error_with_phase2_guidance(self, tmp_path: Path) -> None:
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK fake docx")

        adapter = UnsupportedAdapter()
        result = adapter.convert(docx_file)

        assert result.success is False
        assert result.error_message is not None
        assert "Phase 2" in result.error_message or "Phase 2+" in result.error_message
        assert result.artifact_payload is not None
        assert result.artifact_payload["suffix"] == ".docx"

    def test_convert_url_returns_unsupported_error(self) -> None:
        adapter = UnsupportedAdapter()
        result = adapter.convert(Path("https://example.com/page"))

        assert result.success is False
        assert result.error_message is not None
        assert "URL" in result.error_message or "url" in result.error_message.lower()
        assert result.artifact_payload is not None
        assert result.artifact_payload["type"] == "url_unsupported"


class TestConverterAdapterRegistry:
    """Tests for the converter registry."""

    def test_convert_markdown(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        content = "# Test"
        md_file.write_text(content)

        registry = ConverterAdapterRegistry()
        result = registry.convert(md_file)

        assert result.success is True
        assert result.converted_text == content

    def test_convert_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><h1>Title</h1></body></html>")

        registry = ConverterAdapterRegistry()
        result = registry.convert(html_file)

        assert result.success is True
        assert "# Title" in result.converted_text

    def test_convert_pdf_returns_error(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        registry = ConverterAdapterRegistry()
        result = registry.convert(pdf_file)

        assert result.success is False
        assert result.error_message is not None
        assert "Phase 2" in result.error_message


class TestConvertInput:
    """Tests for the module-level convert_input function."""

    def test_convert_input_html(self, tmp_path: Path) -> None:
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><p>Hello</p></body></html>")

        result = convert_input(html_file)

        assert result.success is True
        assert "Hello" in result.converted_text

    def test_convert_input_markdown(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test.md"
        content = "# Markdown Content"
        md_file.write_text(content)

        result = convert_input(md_file)

        assert result.success is True
        assert result.converted_text == content

    def test_convert_input_pdf_failure(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        result = convert_input(pdf_file)

        assert result.success is False
        assert "Phase 2" in result.error_message
        assert result.artifact_payload is not None


class TestConversionResult:
    """Tests for ConversionResult dataclass."""

    def test_successful_result(self) -> None:
        result = ConversionResult(
            success=True,
            converted_text="# Test",
            source_type="markdown_file",
        )

        assert result.success is True
        assert result.converted_text == "# Test"
        assert result.error_message is None
        assert result.artifact_payload is None
        assert result.source_type == "markdown_file"

    def test_failed_result(self) -> None:
        result = ConversionResult(
            success=False,
            error_message="Conversion failed",
            artifact_payload={"status": "error", "type": "test_error"},
            source_type="pdf",
        )

        assert result.success is False
        assert result.error_message == "Conversion failed"
        assert result.artifact_payload is not None
        assert result.artifact_payload["type"] == "test_error"
        assert result.converted_text is None


class TestUnsupportedSuffixGuidance:
    """Tests that guidance messages are correctly set for Phase 2."""

    def test_pdf_guidance_mentions_phase2(self) -> None:
        assert "Phase 2" in UNSUPPORTED_SUFFIX_GUIDANCE[".pdf"]

    def test_html_guidance_mentions_phase2_builtin(self) -> None:
        assert "Phase 2" in UNSUPPORTED_SUFFIX_GUIDANCE[".html"]
        assert "builtin" in UNSUPPORTED_SUFFIX_GUIDANCE[".html"].lower() or "supported" in UNSUPPORTED_SUFFIX_GUIDANCE[".html"].lower()

    def test_office_guidance_mentions_phase2(self) -> None:
        assert "Phase 2" in UNSUPPORTED_SUFFIX_GUIDANCE[".docx"]
        assert "Phase 2" in UNSUPPORTED_SUFFIX_GUIDANCE[".xlsx"]
