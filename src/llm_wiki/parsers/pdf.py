"""Parser for PDF files using pypdf.

Handles text-based PDFs. Scanned/image PDFs will extract to near-empty text
and be flagged via ParsedDocument.is_empty — the caller decides whether to
skip or still register them.
"""

from __future__ import annotations

from pathlib import Path

from .base import (
    DocumentParser,
    ParsedDocument,
    ParserError,
    compute_hash,
    fallback_title_from_path,
    normalize_text,
)


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) <= 200:
            return line
    return None


class PDFParser(DocumentParser):
    def can_parse(self, suffix: str) -> bool:
        return suffix.lower() == ".pdf"

    def parse(self, path: Path, chunk_size: int = 1500, overlap: int = 200) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ParserError(
                "pypdf is not installed. Run `uv pip install -e .` to install dependencies."
            ) from e

        try:
            reader = PdfReader(str(path))
        except Exception as e:
            raise ParserError(f"Cannot open PDF {path.name}: {e}") from e

        # Resolve wiki assets folder
        from .. import config as cfg
        root = cfg.find_wiki_root(path) or path.parent
        assets_dir = root / "wiki" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Extract text from all pages and extract images
        page_chunks: list[str] = []
        for page_idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            # Extract images from this page
            images_markdown = []
            try:
                # older/newer pypdf interface handle
                images_dict = page.images
                if images_dict:
                    for img_idx, image_file_object in enumerate(images_dict):
                        try:
                            ext = Path(image_file_object.name).suffix or ".png"
                            if ext.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                                ext = ".png"
                            img_name = f"{path.stem}_page_{page_idx + 1}_{img_idx + 1}{ext}"
                            img_path = assets_dir / img_name
                            with open(img_path, "wb") as f:
                                f.write(image_file_object.data)
                            
                            # Store relative markdown reference
                            images_markdown.append(f"![Extracted Slide {page_idx + 1} Image {img_idx + 1}](assets/{img_name})")
                        except Exception:
                            pass
            except Exception:
                pass

            # Combine page text with its images
            if images_markdown:
                page_text += "\n\n" + "\n".join(images_markdown)

            # Only append if non-empty or has images
            if page_text.strip() or images_markdown:
                page_chunks.append(normalize_text(page_text))

        full_text = "\n\n".join(page_chunks)
        text = normalize_text(full_text)

        # Title extraction: metadata first, then first non-empty line, then filename
        title: str | None = None
        try:
            meta = reader.metadata
            if meta and getattr(meta, "title", None):
                meta_title = str(meta.title).strip()
                if meta_title:
                    title = meta_title
        except Exception:
            pass
        if not title:
            title = _first_nonempty_line(text)
        if not title:
            title = fallback_title_from_path(path)

        # Collect useful metadata
        metadata: dict = {"page_count": len(reader.pages)}
        try:
            meta = reader.metadata
            if meta:
                if getattr(meta, "author", None):
                    metadata["author"] = str(meta.author)
                if getattr(meta, "creation_date", None):
                    metadata["creation_date"] = str(meta.creation_date)
        except Exception:
            pass

        return ParsedDocument(
            source_path=path,
            file_type="pdf",
            title=title,
            text=text,
            content_hash=compute_hash(text),
            bytes=path.stat().st_size,
            metadata=metadata,
            chunks=page_chunks,
        )


def parse(path: Path) -> ParsedDocument:
    """Parse a .pdf file."""
    return PDFParser().parse(path)
