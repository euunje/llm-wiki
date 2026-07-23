from __future__ import annotations

from llm_wiki.pipeline.section_chunking import chunk_markdown_by_section


def test_section_chunking_preserves_heading_paths_and_ignores_code_fences(repo_root) -> None:
    source = (repo_root / "testset" / "OKF SPEC.md").read_text(encoding="utf-8")

    chunks = chunk_markdown_by_section(source, max_chars=1200)

    headings = [" > ".join(chunk.heading_path) for chunk in chunks]
    assert any("Concept Documents > Frontmatter" in heading for heading in headings)
    assert any("Conformance" in heading for heading in headings)
    assert any("Versioning" in heading for heading in headings)
    assert all("Optional display name" not in heading for heading in headings)
