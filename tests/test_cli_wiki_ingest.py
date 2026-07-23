from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki.cli import build_parser


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def test_cli_wiki_ingest_writes_real_markdown_pages(workspace: Path, repo_root: Path) -> None:
    _invoke(["init"], workspace)
    source = repo_root / "testset" / "OKF SPEC.md"

    exit_code, payload = _invoke(["ingest", str(source)], workspace)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["page_count"] >= 6
    assert payload["page_count"] <= 20
    assert payload["section_chunk_count"] > payload["page_count"]

    source_summary = workspace / str(payload["source_summary_path"])
    assert source_summary.exists()
    summary_text = source_summary.read_text(encoding="utf-8")
    assert "Generated wiki pages" in summary_text

    page_paths = [workspace / page["path"] for page in payload["wiki_pages"]]
    assert page_paths
    page_bodies = [path.read_text(encoding="utf-8") for path in page_paths]
    assert any("title: Frontmatter" in body or 'title: "Frontmatter"' in body for body in page_bodies)
    assert any("title: Conformance" in body or 'title: "Conformance"' in body for body in page_bodies)
    assert any("title: Versioning" in body or 'title: "Versioning"' in body for body in page_bodies)
    for body in page_bodies:
        assert body.startswith("---\n")
        assert "record_type: knowledge_node" in body
        assert "source_ids:" in body
        assert "tags:" in body
        assert "\n# " in body
        assert "## Source evidence" in body


def _frontmatter(markdown: str) -> dict[str, object]:
    lines = markdown.splitlines()
    assert lines and lines[0].strip() == "---"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return yaml.safe_load("\n".join(lines[1:index])) or {}
    raise AssertionError("missing closing frontmatter fence")


def test_cli_wiki_ingest_forces_source_common_tag_and_node_type_tag(workspace: Path, repo_root: Path) -> None:
    _invoke(["init"], workspace)
    source = repo_root / "testset" / "OKF SPEC.md"

    exit_code, payload = _invoke(["ingest", str(source)], workspace)

    assert exit_code == 0
    assert payload["status"] == "ok"
    quality_gate = payload["quality_gate"]
    assert quality_gate["status"] in {"ok", "repaired"}
    common_tags = set(quality_gate["source_common_tags"])
    assert "okf" in common_tags
    for page in payload["wiki_pages"]:
        fm = _frontmatter((workspace / page["path"]).read_text(encoding="utf-8"))
        tags = set(fm["tags"])
        assert fm["source_ids"] == [payload["source_id"]]
        assert "concept" in tags
        assert common_tags & tags


def test_wiki_ingest_repairs_missing_candidate_metadata_before_compile(monkeypatch, workspace: Path, samples_dir: Path) -> None:
    from llm_wiki.pipeline import wiki_ingest
    from llm_wiki.pipeline.section_chunking import SectionChunk
    from llm_wiki.schema.wiki_page_candidate import WikiPageCandidate

    _invoke(["init"], workspace)

    def broken_extract(workspace_arg, *, source_id: str, source_title: str, chunks: list[SectionChunk], use_llm: bool):
        from llm_wiki.pipeline.wiki_ingest_llm import LLMPageCandidateAttempt
        chunk = chunks[0]
        return [
            WikiPageCandidate(
                candidate_key="page_broken",
                node_type="concept",
                title="Broken Metadata Page",
                summary="",
                source_id="",
                tags=[],
                keywords=[],
                body_outline=[],
                draft_body="",
                source_section_refs=[],
            )
        ], [], LLMPageCandidateAttempt()

    monkeypatch.setattr(wiki_ingest, "extract_wiki_page_candidates_with_optional_llm", broken_extract)

    exit_code, payload = _invoke(["ingest", str(samples_dir / "short-note.md")], workspace)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["page_count"] == 1
    assert payload["quality_gate"]["status"] == "repaired"
    repairs = {repair["action"] for repair in payload["quality_gate"]["repairs"]}
    assert {"set_source_id", "add_common_tags", "fill_body"} <= repairs
    page_text = (workspace / payload["wiki_pages"][0]["path"]).read_text(encoding="utf-8")
    fm = _frontmatter(page_text)
    assert fm["source_ids"] == [payload["source_id"]]
    assert set(fm["tags"]) >= {"short-note", "concept"}
    assert "# Broken Metadata Page" in page_text
