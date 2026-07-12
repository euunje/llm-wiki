"""Tests for safe re-linking logic."""

from __future__ import annotations

import tempfile
from pathlib import Path
from llm_wiki.relinker import relink_references


def test_relink_references():
    with tempfile.TemporaryDirectory() as tmp_dir:
        wiki_dir = Path(tmp_dir)
        
        # Create a file that references the old document
        ref_file = wiki_dir / "concepts" / "another-concept.md"
        ref_file.parent.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(
            "This is a reference to [[some-doc]] and also [[non_categories/some-doc|display text]]\n"
            "Here is a markdown link [Link](../non_categories/some-doc.md) or [direct](non_categories/some-doc.md)\n",
            encoding="utf-8"
        )
        
        # Run relinking
        count = relink_references(wiki_dir, "some-doc", "concepts")
        
        assert count == 1
        
        # Check result content
        content = ref_file.read_text(encoding="utf-8")
        assert "[[concepts/some-doc]]" in content
        assert "[[concepts/some-doc|display text]]" in content
        assert "](../concepts/some-doc.md)" in content
        assert "](concepts/some-doc.md)" in content
