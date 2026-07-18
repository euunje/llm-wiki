"""Phase 1 ingest pipeline and unsupported-input guard tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.pipeline import (
    UnsupportedInputError,
    UserInputError,
    ingest_markdown_file,
)
from llm_wiki.pipeline.hashing import (
    MARKDOWN_SUFFIXES,
    UNSUPPORTED_SUFFIX_GUIDANCE,
    validate_markdown_input,
)
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _ensure_init(workspace: Path) -> None:
    _invoke(["init"], workspace)


def test_validate_markdown_input_accepts_supported_suffix() -> None:
    validate_markdown_input("/tmp/anything.md")
    validate_markdown_input("/tmp/anything.markdown")


def test_validate_markdown_input_rejects_unsupported_suffix() -> None:
    for suffix in UNSUPPORTED_SUFFIX_GUIDANCE:
        with pytest.raises(UnsupportedInputError):
            validate_markdown_input(f"/tmp/sample{suffix}")


def test_validate_markdown_input_rejects_url() -> None:
    with pytest.raises(UnsupportedInputError):
        validate_markdown_input("https://example.com/article")
    with pytest.raises(UnsupportedInputError):
        validate_markdown_input("http://example.com/")


def test_validate_markdown_input_rejects_unknown_suffix() -> None:
    with pytest.raises(UserInputError):
        validate_markdown_input("/tmp/sample.txt")


def test_ingest_creates_source_row_and_stub(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    sample = samples_dir / "short-note.md"
    assert sample.exists()

    exit_code, payload = _invoke(["ingest", str(sample)], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    source_id = payload["source_id"]
    assert source_id.startswith("source_")

    # Stub file lives under vault/10_Wiki/sources/.
    stub_path = workspace / payload["source_stub_path"]
    assert stub_path.exists()
    stub_body = stub_path.read_text(encoding="utf-8")
    assert "Phase 1 source stub" in stub_body

    # After HI-3 fix, ingest no longer pre-creates a queued normalize job
    # (`wiki normalize` owns the canonical normalize job). ingest only
    # returns the artifact id; explicit `wiki normalize` is required.
    assert payload["job_id"] is None
    assert payload["artifact_id"].startswith("artifact_")
    artifact_path = workspace / payload["artifact_path"]
    assert artifact_path.exists()
    stored = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert stored["status"] == "ok"
    assert stored["source_id"] == source_id
    assert stored["normalize_job_id"] is None


def test_ingest_unsupported_pdf_returns_exit_code_2(workspace: Path, tmp_path: Path) -> None:
    _ensure_init(workspace)
    fake_pdf = tmp_path / "paper.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    from llm_wiki.cli import main as cli_main

    exit_code = cli_main(["ingest", str(fake_pdf), "--path", str(workspace)])
    # ValueError/UnsupportedInputError maps to exit code 2 in cli.main.
    assert exit_code == 2


def test_ingest_unsupported_url_returns_exit_code_2(workspace: Path) -> None:
    _ensure_init(workspace)
    from llm_wiki.cli import main as cli_main

    exit_code = cli_main(["ingest", "https://example.com/article", "--path", str(workspace)])
    assert exit_code == 2


def test_ingest_text_creates_user_text_source(workspace: Path) -> None:
    _ensure_init(workspace)
    body = "User typed knowledge from clipboard."

    from llm_wiki.cli import main as cli_main

    exit_code = cli_main(
        ["ingest-text", "Clip note", "--text", body, "--path", str(workspace)]
    )
    assert exit_code == 0


def test_ingest_duplicate_returns_duplicate_status(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    sample = samples_dir / "short-note.md"

    first_exit, first_payload = _invoke(["ingest", str(sample)], workspace)
    assert first_exit == 0
    assert first_payload["status"] == "ok"
    first_source_id = first_payload["source_id"]

    # ingest_markdown_file is the underlying pipeline call; pass the same path
    # in-process to confirm the duplicate code branch without spawning another
    # subprocess.
    paths = resolve_workspace(workspace)
    result = ingest_markdown_file(paths, sample)
    assert result["status"] == "duplicate"
    assert result["source_id"] == first_source_id
