"""Phase 1 normalize → chunk → embed pipeline tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from llm_wiki.cli import build_parser
from llm_wiki.db.schema import connect
from llm_wiki.workspace import resolve_workspace


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _ensure_init(workspace: Path) -> None:
    _invoke(["init"], workspace)


def _ingest(workspace: Path, sample: Path) -> str:
    _, payload = _invoke(["ingest", str(sample)], workspace)
    assert payload["status"] == "ok"
    return payload["source_id"]


def test_normalize_writes_markdown_and_advances_stage(workspace: Path, samples_dir: Path) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "rag.md")

    exit_code, payload = _invoke(["normalize", source_id], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"

    normalized_path = workspace / payload["normalized_path"]
    assert normalized_path.exists()
    body = normalized_path.read_text(encoding="utf-8")
    assert "# Retrieval-Augmented Generation" in body

    # Source pipeline stage advances to "normalized".
    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        stage = conn.execute(
            "SELECT pipeline_stage FROM sources WHERE id = ?", (source_id,)
        ).fetchone()[0]
        assert stage == "normalized"
    finally:
        conn.close()


def test_normalize_rejects_unknown_source(workspace: Path) -> None:
    _ensure_init(workspace)
    from llm_wiki.cli import main as cli_main

    exit_code = cli_main(
        ["normalize", "source_does_not_exist", "--path", str(workspace)]
    )
    assert exit_code == 2


def test_chunk_creates_source_chunks_with_locator(
    workspace: Path, samples_dir: Path
) -> None:
    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "rag.md")
    _invoke(["normalize", source_id], workspace)

    exit_code, payload = _invoke(["chunk", source_id], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["chunk_count"] >= 1
    assert payload["chunk_ids"], "chunk ids must be returned"

    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        rows = conn.execute(
            "SELECT id, token_count, locator_json FROM source_chunks WHERE source_id = ? ORDER BY chunk_index",
            (source_id,),
        ).fetchall()
        assert rows, "source_chunks rows must exist"
        for row in rows:
            assert row[1] > 0
            locator = json.loads(row[2])
            assert locator["source_id"] == source_id
            assert "start_offset" in locator
            assert "end_offset" in locator
            assert locator["char_count"] >= 0
            assert isinstance(locator["heading_path"], list)
    finally:
        conn.close()


def test_embed_uses_deterministic_fallback_when_fastembed_missing(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    """fastembed may be absent in test environments; the embedder should fall
    back to a deterministic hash-based vector and still persist embeddings."""

    _ensure_init(workspace)
    source_id = _ingest(workspace, samples_dir / "short-note.md")
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)

    # Force the fastembed import to fail to exercise the fallback branch.
    import builtins
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "fastembed" or name.startswith("fastembed."):
            raise ImportError("forced fallback for tests")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["embedding_count"] >= 1
    assert payload["dimension"] > 0
    # Phase 1 explicitly names the deterministic fallback backend.
    assert payload["backend"] == "fallback_hash"
    assert payload["model"] == "fallback-hash-v1"

    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        rows = conn.execute(
            "SELECT model, backend, dimension, vector_blob FROM embeddings ORDER BY created_at"
        ).fetchall()
        assert rows
        for model, backend, dimension, blob in rows:
            assert model == "fallback-hash-v1"
            assert backend == "fallback_hash"
            assert dimension > 0
            assert blob is not None and len(blob) > 0
    finally:
        conn.close()


def test_unknown_target_embed_returns_exit_code_2(workspace: Path) -> None:
    _ensure_init(workspace)
    from llm_wiki.cli import main as cli_main

    exit_code = cli_main(["embed", "bogus:abc", "--path", str(workspace)])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# M-1 — Embedder output validation
# ---------------------------------------------------------------------------


class _StubEmbedder:
    """Minimal stand-in for a fastembed ``TextEmbedding`` that returns the
    pre-canned output passed at construction time. The real ``TextEmbedding``
    returns numpy arrays; we use lists of floats for simplicity because
    ``embed_target`` converts via ``list(map(float, vector))`` either way.
    """

    def __init__(self, vectors):
        self._vectors = list(vectors)

    def embed(self, texts):  # noqa: D401 - matches fastembed signature
        return list(self._vectors)


def _stub_embedder_factory(vectors):
    """Build a factory matching ``_load_embedder``'s signature."""

    def _factory(model_name, timeout_seconds):
        return _StubEmbedder(vectors), None

    return _factory


def _drive_through_chunk(workspace: Path, sample: Path) -> str:
    _ensure_init(workspace)
    source_id = _ingest(workspace, sample)
    _invoke(["normalize", source_id], workspace)
    _invoke(["chunk", source_id], workspace)
    return source_id


def test_validate_embedder_output_accepts_well_formed_vectors() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [
        [0.1, 0.2, -0.3, 0.4],
        [-0.5, 0.6, 0.7, -0.8],
        [0.9, -0.1, 0.2, 0.3],
    ]
    validated, reason = _validate_embedder_output(vectors, expected_count=3)
    assert validated is not None
    assert reason is None
    assert validated == vectors


def test_validate_embedder_output_rejects_empty_list() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    validated, reason = _validate_embedder_output([], expected_count=2)
    assert validated is None
    assert reason is not None
    assert "no vectors" in reason or "0 vectors" in reason


def test_validate_embedder_output_rejects_short_list() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [[0.1, 0.2, 0.3, 0.4]]
    validated, reason = _validate_embedder_output(vectors, expected_count=2)
    assert validated is None
    assert reason is not None
    assert "1 vectors" in reason
    assert "2 targets" in reason


def test_validate_embedder_output_rejects_mismatched_dimensions() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [
        [0.1, 0.2, 0.3, 0.4],
        [-0.5, 0.6, 0.7],  # dimension 3 instead of 4
        [0.9, -0.1, 0.2, 0.3],
    ]
    validated, reason = _validate_embedder_output(vectors, expected_count=3)
    assert validated is None
    assert reason is not None
    assert "dimension 3" in reason
    assert "expected 4" in reason


def test_validate_embedder_output_rejects_all_zero_vector() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [
        [0.1, 0.2, 0.3, 0.4],
        [0.0, 0.0, 0.0, 0.0],  # all zero
        [0.9, -0.1, 0.2, 0.3],
    ]
    validated, reason = _validate_embedder_output(vectors, expected_count=3)
    assert validated is None
    assert reason is not None
    assert "vector 1" in reason
    assert "all-zero" in reason


def test_validate_embedder_output_rejects_non_numeric_values() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [
        [0.1, 0.2, 0.3, 0.4],
        ["a", "b", "c", "d"],
    ]
    validated, reason = _validate_embedder_output(vectors, expected_count=2)
    assert validated is None
    assert reason is not None
    assert "non-numeric" in reason


def test_validate_embedder_output_rejects_zero_dimension() -> None:
    from llm_wiki.pipeline.embed import _validate_embedder_output

    vectors = [[], [0.1, 0.2]]
    validated, reason = _validate_embedder_output(vectors, expected_count=2)
    assert validated is None
    assert reason is not None
    assert "zero dimension" in reason


def test_embed_falls_back_when_embedder_returns_empty_output(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    """Empty output (0 vectors) must never be persisted; the embed command
    must fall back to ``fallback_hash`` with an explicit reason in
    ``backend_detail`` instead of silently succeeding."""
    import llm_wiki.pipeline.embed as embed_module

    source_id = _drive_through_chunk(workspace, samples_dir / "short-note.md")
    monkeypatch.setattr(
        embed_module, "_load_embedder", _stub_embedder_factory([])
    )

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["backend"] == "fallback_hash"
    assert payload["model"] == "fallback-hash-v1"
    detail = payload.get("backend_detail") or {}
    assert "embedder output invalid" in detail.get("reason", "")
    assert "no vectors" in detail.get("reason", "") or "0 vectors" in detail.get(
        "reason", ""
    )


def test_embed_falls_back_when_embedder_returns_short_output(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    """Short output (1 vector when 2 expected) must trigger fallback; the
    silent ``zip`` truncation that previously allowed inconsistent state
    is no longer reachable."""
    import llm_wiki.pipeline.embed as embed_module

    # rag.md produces 2 chunks under the default chunking settings.
    source_id = _drive_through_chunk(workspace, samples_dir / "rag.md")
    # Only one vector returned for a source that has 2 chunks.
    monkeypatch.setattr(
        embed_module,
        "_load_embedder",
        _stub_embedder_factory([[0.1, 0.2, 0.3, 0.4]]),
    )

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["backend"] == "fallback_hash"
    assert payload["model"] == "fallback-hash-v1"
    detail = payload.get("backend_detail") or {}
    assert "embedder output invalid" in detail.get("reason", "")
    assert "1 vectors" in detail.get("reason", "")
    # Confirm no embedding rows were persisted for the rejected fastembed run.
    paths = resolve_workspace(workspace)
    conn = connect(paths.db)
    try:
        rows = conn.execute(
            "SELECT model, backend FROM embeddings WHERE model != 'fallback-hash-v1'"
        ).fetchall()
        assert not rows, f"fastembed rows must not be persisted on validation failure: {rows}"
    finally:
        conn.close()


def test_embed_falls_back_when_embedder_returns_mismatched_dimensions(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    import llm_wiki.pipeline.embed as embed_module

    # rag.md produces section-aware chunks; provide the same target count so the
    # dimension mismatch check is what triggers the fallback.
    source_id = _drive_through_chunk(workspace, samples_dir / "rag.md")
    monkeypatch.setattr(
        embed_module,
        "_load_embedder",
        _stub_embedder_factory(
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.2, 0.3, 0.4, 0.5],
                [-0.5, 0.6, 0.7],  # dimension 3 vs 4
            ]
        ),
    )

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["backend"] == "fallback_hash"
    detail = payload.get("backend_detail") or {}
    assert "embedder output invalid" in detail.get("reason", "")
    assert "dimension 3" in detail.get("reason", "")
    assert "expected 4" in detail.get("reason", "")


def test_embed_falls_back_when_embedder_returns_all_zero_vectors(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    import llm_wiki.pipeline.embed as embed_module

    # rag.md produces section-aware chunks; one of them returns an all-zero vector
    # so the validator falls back explicitly.
    source_id = _drive_through_chunk(workspace, samples_dir / "rag.md")
    monkeypatch.setattr(
        embed_module,
        "_load_embedder",
        _stub_embedder_factory(
            [
                [0.1, 0.2, 0.3, 0.4],
                [0.2, 0.3, 0.4, 0.5],
                [0.0, 0.0, 0.0, 0.0],  # all-zero
            ]
        ),
    )

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["backend"] == "fallback_hash"
    detail = payload.get("backend_detail") or {}
    assert "embedder output invalid" in detail.get("reason", "")
    assert "all-zero" in detail.get("reason", "")


def test_embed_succeeds_with_valid_fastembed_output(
    workspace: Path, samples_dir: Path, monkeypatch
) -> None:
    """Positive control: when the embedder output is well-formed, the
    embed command reports ``backend: fastembed`` and persists real
    embedding rows. This guards against the fallback being triggered
    unnecessarily."""
    import llm_wiki.pipeline.embed as embed_module

    source_id = _drive_through_chunk(workspace, samples_dir / "rag.md")
    monkeypatch.setattr(
        embed_module,
        "_load_embedder",
        _stub_embedder_factory(
            [
                [0.1, 0.2, -0.3, 0.4],
                [-0.5, 0.6, 0.7, -0.8],
                [0.9, -0.1, 0.2, -0.3],
            ]
        ),
    )

    exit_code, payload = _invoke(["embed", f"source:{source_id}"], workspace)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["backend"] == "fastembed"
    assert payload["dimension"] == 4
    # backend_detail must NOT be set when fastembed succeeds.
    assert "backend_detail" not in payload or not payload["backend_detail"]
