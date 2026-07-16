from __future__ import annotations

import json
import re

import pytest
import yaml

from llm_wiki import config as cfg
from llm_wiki import db
from llm_wiki.ingest_llm import (
    ChunkExtraction,
    IngestCallbacks,
    LLMError,
    _aggregate_chunk_extractions,
    _exact_slug_candidates,
    _extract_chunked,
    _resolve_slug,
    ingest_source,
)
from llm_wiki.parsers.base import ParsedDocument


def _write_runtime_config(vault_root, runtime, *, max_source_chars: int = 100_000):
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "config.yml").write_text(
        yaml.safe_dump(
            {
                "paths": {
                    "root": str(vault_root),
                    "raw_dir": "10. Raw Sources",
                    "internal_dir": str(runtime),
                    "wiki_dir": "20. Wiki",
                    "page_dirs": {
                        "sources": "20. Wiki/20. Sources",
                        "entities": "20. Wiki/22. Entities",
                        "concepts": "20. Wiki/21. Concepts",
                        "synthesis": "30. Queries",
                        "non_categories": "00. Inbox/_Review",
                    },
                    "files": {"state_db": str(runtime / "state.sqlite")},
                },
                "ingest": {"max_source_chars": max_source_chars},
            }
        ),
        encoding="utf-8",
    )


def _register_source(paths, relpath: str, text: str) -> int:
    source_path = paths.root / relpath
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(text, encoding="utf-8")
    db.init_db(paths.state_db)
    with db.connect(paths.state_db) as conn:
        conn.execute(
            """
            INSERT INTO sources (relpath, content_hash, file_type, bytes, added_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (relpath, f"hash-{relpath}", "markdown", source_path.stat().st_size, "2026-07-16T00:00:00Z", "pending"),
        )
        return conn.execute("SELECT id FROM sources ORDER BY id DESC LIMIT 1").fetchone()[0]


def _make_doc(source_path, *, text: str, chunks: list[str]) -> ParsedDocument:
    return ParsedDocument(
        source_path=source_path,
        file_type="markdown",
        title="Chunk Test Source",
        text=text,
        content_hash="hash-doc",
        bytes=len(text.encode("utf-8")),
        chunks=chunks,
    )


class _RecordingCallbacks(IngestCallbacks):
    def __init__(self):
        self.chunk_started: list[tuple[int, int]] = []
        self.chunk_done: list[int] = []
        self.chunk_failed: list[tuple[int, int, str]] = []
        self.extractions = 0

    def on_chunk_extracting(self, chunk_index: int, total_chunks: int) -> None:
        self.chunk_started.append((chunk_index, total_chunks))

    def on_chunk_extracted(self, chunk: ChunkExtraction, total_chunks: int) -> None:
        self.chunk_done.append(chunk.chunk_index)

    def on_chunk_extraction_failed(self, chunk_index: int, total_chunks: int, error: str) -> None:
        self.chunk_failed.append((chunk_index, total_chunks, error))

    def on_extracted(self, extraction) -> None:
        self.extractions += 1


class _ChunkAwareFakeClient:
    provider = "ollama"

    def __init__(
        self,
        *,
        single_response: str | None = None,
        chunk_responses: dict[int, str | list[str]] | None = None,
        single_error_once: str | None = None,
    ):
        self.single_response = single_response
        self.chunk_responses = chunk_responses or {}
        self.single_error_once = single_error_once
        self.single_calls = 0
        self.chunk_calls: list[int] = []
        self._chunk_response_offsets: dict[int, int] = {}

    def chat(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        if "---CHUNK INDEX---" in prompt:
            chunk_index = int(re.search(r"---CHUNK INDEX---\n(\d+)", prompt).group(1))
            self.chunk_calls.append(chunk_index)
            response = self.chunk_responses[chunk_index]
            if isinstance(response, list):
                offset = self._chunk_response_offsets.get(chunk_index, 0)
                self._chunk_response_offsets[chunk_index] = offset + 1
                return response[min(offset, len(response) - 1)]
            return response
        if "---SOURCE TEXT---" in prompt and "key_takeaways" in prompt and "candidates" in prompt:
            self.single_calls += 1
            if self.single_error_once and self.single_calls == 1:
                raise LLMError(self.single_error_once)
            return self.single_response or "{}"
        return self.single_response or "{}"

    def chat_stream(self, messages, **kwargs):
        prompt = "\n".join(m.content for m in messages)
        source_slug_match = re.search(r"sources/([a-z0-9-]+)\.md", prompt)
        source_slug = source_slug_match.group(1) if source_slug_match else "chunk-test-source"
        if "source summary page" in prompt:
            text = (
                "---\n"
                "title: Chunk Test Source\n"
                "type: source\n"
                "tags: [chunk]\n"
                "created: 2026-07-16\n"
                "updated: 2026-07-16\n"
                "file_path: /api/raw-download/1\n"
                "file_type: markdown\n"
                "---\n\n"
                "# Chunk Test Source\n\n"
                "요약.\n"
            )
        else:
            kind_match = re.search(r'- type: (entity|concept)', prompt)
            slug_match = re.search(r'- slug: ([a-z0-9-]+)', prompt)
            kind = kind_match.group(1) if kind_match else "entity"
            slug = slug_match.group(1) if slug_match else "item"
            title = slug.replace("-", " ").title()
            text = json.dumps(
                {
                    "slug": slug,
                    "type": kind,
                    "body_markdown": f"# {title}\n\n설명.\n\n## 출처\n\n[[sources/{source_slug}]]\n",
                    "links_used": [f"sources/{source_slug}"],
                    "sources": [f"sources/{source_slug}.md"],
                }
            )
        if False:
            yield ""
        return text


def test_small_document_still_uses_single_extraction(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    runtime = vault_root / ".wiki"
    _write_runtime_config(vault_root, runtime, max_source_chars=1000)
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_source(paths, "10. Raw Sources/small.md", "small")
    parsed = _make_doc(paths.root / "10. Raw Sources/small.md", text="short text", chunks=["short text"])
    monkeypatch.setattr("llm_wiki.ingest_llm.parsers.parse", lambda *args, **kwargs: parsed)
    monkeypatch.setattr("llm_wiki.ingest_llm._lint_changed_pages", lambda *args, **kwargs: [])

    client = _ChunkAwareFakeClient(
        single_response=json.dumps(
            {
                "title": "Chunk Test Source",
                "source_slug": "chunk-test-source",
                "summary": "짧은 문서 요약",
                "key_takeaways": ["하나"],
                "candidates": [
                    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "설명", "confidence": "high"}
                ],
                "entities": [],
                "concepts": [],
                "tags": ["chunk"],
            }
        )
    )
    callbacks = _RecordingCallbacks()

    result = ingest_source(paths, source_id, client, callbacks, mode="batch", thinking_for_extraction=False)

    assert result.ok, result.error
    assert client.single_calls == 1
    assert client.chunk_calls == []
    assert callbacks.chunk_started == []


def test_large_document_uses_chunks_and_preserves_late_candidate(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    runtime = vault_root / ".wiki"
    _write_runtime_config(vault_root, runtime, max_source_chars=20)
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_source(paths, "10. Raw Sources/large.md", "large")
    parsed = _make_doc(
        paths.root / "10. Raw Sources/large.md",
        text="a" * 120,
        chunks=["chunk 0 about OpenAI", "chunk 1 about Map Reduce"],
    )
    monkeypatch.setattr("llm_wiki.ingest_llm.parsers.parse", lambda *args, **kwargs: parsed)
    monkeypatch.setattr("llm_wiki.ingest_llm._lint_changed_pages", lambda *args, **kwargs: [])

    client = _ChunkAwareFakeClient(
        chunk_responses={
            0: json.dumps(
                {
                    "chunk_index": 0,
                    "chunk_summary": "첫 청크 요약",
                    "key_takeaways": ["OpenAI 언급"],
                    "candidates": [
                        {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "첫 설명", "confidence": "high"}
                    ],
                    "tags": ["ai"],
                    "confidence": "high",
                }
            ),
            1: json.dumps(
                {
                    "chunk_index": 1,
                    "chunk_summary": "둘째 청크 요약",
                    "key_takeaways": ["Map Reduce 언급"],
                    "candidates": [
                        {"name": "Map Reduce", "slug": "map-reduce", "pageKind": "concept", "description": "늦은 청크 설명", "confidence": "medium"}
                    ],
                    "tags": ["systems"],
                    "confidence": "medium",
                }
            ),
        }
    )
    callbacks = _RecordingCallbacks()

    result = ingest_source(paths, source_id, client, callbacks, mode="batch", thinking_for_extraction=False)

    assert result.ok, result.error
    assert client.single_calls == 0
    assert client.chunk_calls == [0, 1]
    assert callbacks.chunk_started == [(0, 2), (1, 2)]
    assert callbacks.chunk_done == [0, 1]
    changed_slugs = {change.slug for change in result.changes}
    assert "openai" in changed_slugs
    assert "map-reduce" in changed_slugs


def test_context_overflow_in_single_extraction_falls_back_to_chunked(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    runtime = vault_root / ".wiki"
    _write_runtime_config(vault_root, runtime, max_source_chars=500)
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_source(paths, "10. Raw Sources/fallback.md", "fallback")
    parsed = _make_doc(
        paths.root / "10. Raw Sources/fallback.md",
        text="fits configured threshold",
        chunks=["chunk 0", "chunk 1"],
    )
    monkeypatch.setattr("llm_wiki.ingest_llm.parsers.parse", lambda *args, **kwargs: parsed)
    monkeypatch.setattr("llm_wiki.ingest_llm._lint_changed_pages", lambda *args, **kwargs: [])

    client = _ChunkAwareFakeClient(
        single_response=json.dumps(
            {
                "title": "Chunk Test Source",
                "source_slug": "chunk-test-source",
                "summary": "single",
                "key_takeaways": ["single"],
                "candidates": [],
                "entities": [],
                "concepts": [],
                "tags": [],
            }
        ),
        chunk_responses={
            0: json.dumps(
                {
                    "chunk_index": 0,
                    "chunk_summary": "청크 0",
                    "key_takeaways": ["하나"],
                    "candidates": [
                        {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "설명", "confidence": "high"}
                    ],
                    "tags": ["ai"],
                }
            ),
            1: json.dumps(
                {
                    "chunk_index": 1,
                    "chunk_summary": "청크 1",
                    "key_takeaways": ["둘"],
                    "candidates": [],
                    "tags": ["ai"],
                }
            ),
        },
        single_error_once="Ollama error 400: prompt greater than context length",
    )

    result = ingest_source(paths, source_id, client, _RecordingCallbacks(), mode="batch", thinking_for_extraction=False)

    assert result.ok, result.error
    assert client.single_calls == 1
    assert client.chunk_calls == [0, 1]


def test_generic_500_context_length_error_does_not_fall_back_to_chunked(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    vault_root = tmp_path / "vault"
    runtime = vault_root / ".wiki"
    _write_runtime_config(vault_root, runtime, max_source_chars=500)
    paths = cfg.WikiPaths(vault_root)
    source_id = _register_source(paths, "10. Raw Sources/no-fallback.md", "fallback")
    parsed = _make_doc(
        paths.root / "10. Raw Sources/no-fallback.md",
        text="fits configured threshold",
        chunks=["chunk 0", "chunk 1"],
    )
    monkeypatch.setattr("llm_wiki.ingest_llm.parsers.parse", lambda *args, **kwargs: parsed)
    monkeypatch.setattr("llm_wiki.ingest_llm._lint_changed_pages", lambda *args, **kwargs: [])

    client = _ChunkAwareFakeClient(
        single_response="{}",
        chunk_responses={0: "{}", 1: "{}"},
        single_error_once="server error 500: context length metadata unavailable",
    )

    result = ingest_source(paths, source_id, client, _RecordingCallbacks(), mode="batch", thinking_for_extraction=False)

    assert not result.ok
    assert "LLM error" in result.error
    assert client.single_calls == 1
    assert client.chunk_calls == []


def test_chunk_retry_parse_failure_emits_failed_callback_once(tmp_path):
    parsed = _make_doc(tmp_path / "source.md", text="chunked text", chunks=["chunk 0"])
    client = _ChunkAwareFakeClient(
        chunk_responses={
            0: [
                '{"chunk_summary": "missing close brace"',
                '{"chunk_summary": "still broken"',
            ]
        }
    )
    callbacks = _RecordingCallbacks()

    with pytest.raises(ValueError, match="Invalid chunk JSON"):
        _extract_chunked(parsed=parsed, client=client, callbacks=callbacks, db_path=tmp_path / "state.sqlite")

    assert client.chunk_calls == [0, 0]
    assert callbacks.chunk_failed and len(callbacks.chunk_failed) == 1
    assert callbacks.chunk_failed[0][:2] == (0, 1)


def test_exact_slug_candidates_distinguish_non_categories_from_entities(tmp_path):
    vault_root = tmp_path / "vault"
    runtime = vault_root / ".wiki"
    _write_runtime_config(vault_root, runtime)
    paths = cfg.WikiPaths(vault_root)
    paths.entities.mkdir(parents=True, exist_ok=True)
    paths.non_categories.mkdir(parents=True, exist_ok=True)
    (paths.entities / "openai.md").write_text("---\ntitle: OpenAI\n---\n", encoding="utf-8")
    (paths.non_categories / "openai.md").write_text("---\ntitle: OpenAI\n---\n", encoding="utf-8")

    exact_matches = _exact_slug_candidates("entity", paths, "OpenAI", "openai")
    plan = _resolve_slug("OpenAI", "entity", paths, "openai")

    assert exact_matches == [
        ("entities/openai", paths.entities / "openai.md"),
        ("non_categories/openai", paths.non_categories / "openai.md"),
    ]
    assert plan.action == "needs_review"
    assert plan.canonical_slug == "entities/openai"
    assert plan.final_path is None


def test_aggregation_dedupes_candidate_slugs_and_combines_summaries_and_takeaways():
    aggregated = _aggregate_chunk_extractions(
        "Chunk Test Source",
        "chunk-test-source",
        [
            ChunkExtraction(
                chunk_index=0,
                chunk_summary="첫 요약",
                key_takeaways=["하나", "공통"],
                candidates=[
                    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "짧은 설명", "confidence": "low"}
                ],
                tags=["ai"],
            ),
            ChunkExtraction(
                chunk_index=1,
                chunk_summary="둘 요약",
                key_takeaways=["둘", "공통"],
                candidates=[
                    {"name": "OpenAI", "slug": "openai", "pageKind": "entity", "description": "더 긴 설명", "confidence": "high"},
                    {"name": "RAG", "slug": "rag", "pageKind": "concept", "description": "개념", "confidence": "medium"},
                ],
                tags=["retrieval"],
            ),
        ],
    )

    assert [candidate.slug for candidate in aggregated.candidates] == ["openai", "rag"]
    assert aggregated.candidates[0].description == "더 긴 설명"
    assert aggregated.candidates[0].confidence == "high"
    assert aggregated.summary == "첫 요약 둘 요약"
    assert aggregated.key_takeaways == ["하나", "공통", "둘"]
    assert aggregated.tags == ["ai", "retrieval"]
