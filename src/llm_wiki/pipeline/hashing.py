from __future__ import annotations

from pathlib import Path

from llm_wiki.common import sha256_bytes, sha256_text
from llm_wiki.pipeline.errors import UnsupportedInputError, UserInputError


MARKDOWN_SUFFIXES = {".md", ".markdown"}
UNSUPPORTED_SUFFIX_GUIDANCE = {
    ".pdf": "PDF import is planned for Phase 2 conversion support.",
    ".doc": "Office import is planned for Phase 2 conversion support.",
    ".docx": "Office import is planned for Phase 2 conversion support.",
    ".ppt": "Office import is planned for Phase 2 conversion support.",
    ".pptx": "Office import is planned for Phase 2 conversion support.",
    ".xls": "Office import is planned for Phase 2 conversion support.",
    ".xlsx": "Office import is planned for Phase 2 conversion support.",
    ".html": "HTML import is planned for Phase 2 conversion support.",
    ".htm": "HTML import is planned for Phase 2 conversion support.",
}


def hash_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def hash_text(text: str) -> str:
    return sha256_text(text)


def validate_markdown_input(raw: str) -> None:
    if raw.startswith(("http://", "https://")):
        raise UnsupportedInputError(
            "URL ingest is unsupported in Phase 1. Phase 2 will add URL-to-Markdown conversion."
        )
    suffix = Path(raw).suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        return
    if suffix in UNSUPPORTED_SUFFIX_GUIDANCE:
        raise UnsupportedInputError(
            f"Unsupported input type '{suffix}'. {UNSUPPORTED_SUFFIX_GUIDANCE[suffix]}"
        )
    raise UserInputError("Phase 1 ingest accepts Markdown files only (.md, .markdown).")
