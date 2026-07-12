"""Tests for document parsers registry and chunking."""

from __future__ import annotations

import tempfile
from pathlib import Path
from llm_wiki.parsers import parse, is_supported
from llm_wiki.parsers.base import chunk_text_sliding


def test_chunk_text_sliding():
    text = "This is a simple text that needs to be chunked into pieces."
    chunks = chunk_text_sliding(text, chunk_size=20, overlap=5)
    assert len(chunks) > 1
    # Check that chunks are split near spaces (word boundary)
    for c in chunks:
        assert len(c) <= 20


def test_parsers_registry_txt():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Line 1\nLine 2\nThis is the content.")
        path = Path(f.name)
        
    try:
        assert is_supported(path)
        doc = parse(path, chunk_size=15, overlap=2)
        assert doc.file_type == "txt"
        assert len(doc.chunks) > 0
    finally:
        path.unlink()
