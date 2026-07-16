"""LLM ingest pipeline — the orchestrator for `wiki ingest`.

Three-pass flow per source:
    1. EXTRACT — JSON: summary, candidates, takeaways
    2. DRAFT  — one wiki page per entity/concept candidate; review candidates
                are staged deterministically in non_categories/
    3. SOURCE — the sources/<slug>.md summary page

After all passes: index.md is rebuilt and log.md is appended.

Transactional: pages are staged and only committed to wiki/ on success.
The DB source status flips to 'ingested' only after a full successful run.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field, ValidationError

from . import config as cfg
from . import db
from . import lint
from . import page_writer
from . import parsers
from . import prompts
from . import slugify
from .llm import (
    LLMError,
    ModelNotFound,
    OllamaClient,
    OllamaNotRunning,
)


MAX_SOURCE_CHARS = 100_000  # ~25K tokens roughly
EXCERPT_CHARS = 4000        # how much of the source we include in draft prompts
OPENAI_LOCAL_MAX_SOURCE_CHARS = 25_000


# ---------------------------------------------------------------------------
# Pydantic models for Pass 1 JSON validation
# ---------------------------------------------------------------------------


class ExtractedCandidate(BaseModel):
    name: str
    slug: str
    pageKind: str = "entity"  # "entity" | "concept" | "review"
    description: str = ""
    confidence: str | float | None = None  # "high" | "medium" | "low" | float
    suggestedExternalOwner: str | None = None  # "8000-web-config" | "mcp-map"
    reason: str | None = None


class ExtractedEntity(BaseModel):
    name: str
    slug: str
    type: str = "entity"
    description: str


class ExtractedConcept(BaseModel):
    name: str
    slug: str
    type: str = "concept"
    description: str


class Extraction(BaseModel):
    title: str
    source_slug: str
    summary: str
    key_takeaways: list[str] = Field(default_factory=list)
    candidates: list[ExtractedCandidate] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ChunkExtraction(BaseModel):
    chunk_index: int
    chunk_summary: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    candidates: list[ExtractedCandidate] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: str | float | None = None


class GeneratedPage(BaseModel):
    slug: str
    type: str
    body_markdown: str
    links_used: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class _StreamCallbackError(LLMError):
    """Raised when streaming callbacks fail during generation."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PageChange:
    slug: str
    path: str       # relative to wiki root, e.g. 'entities/karpathy.md'
    kind: str       # 'entity' | 'concept' | 'source'
    operation: str  # 'created' | 'updated'


@dataclass
class IngestResult:
    source_id: int
    source_title: str
    source_slug: str
    pages_created: int = 0
    pages_updated: int = 0
    changes: list[PageChange] = field(default_factory=list)
    error: str | None = None
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and not self.skipped


@dataclass
class ResolutionPlan:
    item: ExtractedEntity | ExtractedConcept | None
    kind: str
    slug: str
    canonical_slug: str
    action: str  # create | merge | needs_review
    exists: bool = False
    final_path: Path | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Progress callback interface
# ---------------------------------------------------------------------------


class IngestCallbacks:
    """Hooks the CLI provides to render progress during ingest.

    All methods have default no-ops. The CLI subclasses to add rich output.
    """

    def on_start(self, source_id: int, source_title: str, file_path: str) -> None: ...

    def on_parsing(self) -> None: ...

    def on_extracting(self) -> None: ...

    def on_chunk_extracting(self, chunk_index: int, total_chunks: int) -> None: ...

    def on_chunk_extracted(self, chunk: ChunkExtraction, total_chunks: int) -> None: ...

    def on_chunk_extraction_failed(self, chunk_index: int, total_chunks: int, error: str) -> None: ...

    def on_extracted(self, extraction: Extraction) -> None: ...

    def on_extraction_failed(self, error: str) -> None: ...

    def ask_confirm(self, extraction: Extraction) -> bool:
        """Interactive confirmation before writing pages. Default: yes."""
        return True

    def on_drafting_page(self, kind: str, slug: str, operation: str) -> None: ...

    def on_stream_chunk(self, chunk: str) -> None: ...

    def on_page_written(self, page: PageChange) -> None: ...

    def on_finalizing(self) -> None: ...

    def on_complete(self, result: IngestResult) -> None: ...

    def on_error(self, error: str) -> None: ...


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> str:
    """Find the first top-level {...} block in text. Robust to extra prose."""
    text = text.strip()
    # Strip possible markdown fences
    if text.startswith("```"):
        lines = text.split("\n", 1)
        if len(lines) == 2:
            text = lines[1]
        if text.rstrip().endswith("```"):
            text = text.rsplit("```", 1)[0]

    start = text.find("{")
    if start == -1:
        return text
    # Find matching closing brace
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _normalize_extraction_data(data: dict) -> dict:
    """Normalize old/new extraction JSON into one internal contract.

    ``candidates[]`` is the Phase 2 source of truth when present.  Legacy
    ``entities[]``/``concepts[]`` remain accepted and are converted into
    candidates.  For backward compatibility with CLI/jobs and the existing
    draft loops, entity/concept candidates are also projected back into the
    legacy arrays.
    """
    candidates = data.get("candidates") or []
    if candidates:
        normalized_candidates = []
        entities = []
        concepts = []
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("pageKind") or raw.get("type") or "entity").strip().lower()
            if kind not in {"entity", "concept", "review"}:
                kind = "review"
            item = {**raw, "pageKind": kind}
            normalized_candidates.append(item)
            if kind == "entity":
                entities.append(
                    {
                        "name": item.get("name", ""),
                        "slug": item.get("slug", ""),
                        "type": "entity",
                        "description": item.get("description", ""),
                    }
                )
            elif kind == "concept":
                concepts.append(
                    {
                        "name": item.get("name", ""),
                        "slug": item.get("slug", ""),
                        "type": "concept",
                        "description": item.get("description", ""),
                    }
                )
        data["candidates"] = normalized_candidates
        data["entities"] = entities
        data["concepts"] = concepts
        return data

    # Legacy response: derive candidates while preserving original arrays.
    derived = []
    for ent in data.get("entities", []) or []:
        if not isinstance(ent, dict):
            continue
        derived.append(
            {
                "name": ent.get("name", ""),
                "slug": ent.get("slug", ""),
                "pageKind": "entity",
                "description": ent.get("description", ""),
                "confidence": None,
                "suggestedExternalOwner": None,
                "reason": None,
            }
        )
    for con in data.get("concepts", []) or []:
        if not isinstance(con, dict):
            continue
        derived.append(
            {
                "name": con.get("name", ""),
                "slug": con.get("slug", ""),
                "pageKind": "concept",
                "description": con.get("description", ""),
                "confidence": None,
                "suggestedExternalOwner": None,
                "reason": None,
            }
        )
    if derived:
        data["candidates"] = derived
    return data


def _parse_extraction(raw: str) -> Extraction:
    """Parse the JSON from Pass 1, raising ValueError on failure.

    Normalizes the response so that both the legacy entities[]/concepts[] format
    and the new candidates[] format are available on the returned Extraction object.
    """
    json_str = _extract_json_object(raw)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e
    try:
        return Extraction(**_normalize_extraction_data(data))
    except ValidationError as e:
        raise ValueError(f"JSON didn't match expected schema: {e}") from e


def _parse_chunk_extraction(raw: str, *, expected_chunk_index: int | None = None) -> ChunkExtraction:
    """Parse chunk extraction JSON, allowing omitted chunk_index via caller context."""
    json_str = _extract_json_object(raw)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid chunk JSON from LLM: {e}") from e
    if expected_chunk_index is not None and "chunk_index" not in data:
        data["chunk_index"] = expected_chunk_index
    try:
        return ChunkExtraction(**_normalize_extraction_data(data))
    except ValidationError as e:
        raise ValueError(f"Chunk JSON didn't match expected schema: {e}") from e


def _build_excerpt(text: str, max_chars: int = EXCERPT_CHARS) -> str:
    """Return a trimmed snippet of the source text suitable for draft prompts."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... truncated ...]"


def _normalize_confidence_rank(value: str | float | None) -> int:
    if isinstance(value, (int, float)):
        if value >= 0.85:
            return 3
        if value >= 0.65:
            return 2
        return 1
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "high":
            return 3
        if normalized == "medium":
            return 2
        if normalized:
            return 1
    return 0


def _merge_candidate(existing: ExtractedCandidate, incoming: ExtractedCandidate) -> ExtractedCandidate:
    description = existing.description
    if len((incoming.description or "").strip()) >= len((description or "").strip()):
        description = incoming.description
    confidence = existing.confidence
    if _normalize_confidence_rank(incoming.confidence) >= _normalize_confidence_rank(existing.confidence):
        confidence = incoming.confidence
    page_kind = existing.pageKind
    if existing.pageKind != incoming.pageKind:
        if "review" in {existing.pageKind, incoming.pageKind}:
            page_kind = "review"
        elif incoming.pageKind:
            page_kind = incoming.pageKind
    return ExtractedCandidate(
        name=incoming.name or existing.name,
        slug=incoming.slug or existing.slug,
        pageKind=page_kind,
        description=description,
        confidence=confidence,
        suggestedExternalOwner=incoming.suggestedExternalOwner or existing.suggestedExternalOwner,
        reason=incoming.reason or existing.reason,
    )


def _aggregate_chunk_extractions(
    source_title: str,
    source_slug: str,
    chunk_extractions: list[ChunkExtraction],
) -> Extraction:
    ordered_chunks = sorted(chunk_extractions, key=lambda item: item.chunk_index)
    candidate_map: dict[str, ExtractedCandidate] = {}
    ordered_candidate_keys: list[str] = []
    summaries: list[str] = []
    key_takeaways: list[str] = []
    tags: list[str] = []

    for chunk in ordered_chunks:
        summary = chunk.chunk_summary.strip()
        if summary:
            summaries.append(summary)
        key_takeaways.extend(item.strip() for item in chunk.key_takeaways if item and item.strip())
        tags.extend(item.strip() for item in chunk.tags if item and item.strip())
        for candidate in chunk.candidates:
            dedupe_key = slugify.slugify(candidate.slug or candidate.name) or (candidate.name or "").strip().casefold()
            if not dedupe_key:
                continue
            if dedupe_key in candidate_map:
                candidate_map[dedupe_key] = _merge_candidate(candidate_map[dedupe_key], candidate)
            else:
                candidate_map[dedupe_key] = candidate
                ordered_candidate_keys.append(dedupe_key)

    summary = " ".join(_dedupe_preserve_order(summaries)).strip()
    if not summary:
        summary = f"{source_title}의 여러 문서 청크에서 추출한 요약입니다."

    data = {
        "title": source_title,
        "source_slug": source_slug,
        "summary": summary,
        "key_takeaways": _dedupe_preserve_order(key_takeaways),
        "candidates": [candidate_map[key].model_dump() for key in ordered_candidate_keys],
        "tags": _dedupe_preserve_order(tags)[:5],
    }
    return Extraction(**_normalize_extraction_data(data))


def _is_context_overflow_error(error: Exception) -> bool:
    message = str(error).lower()
    overflow_phrases = (
        "prompt greater than context length",
        "context length",
        "maximum context length",
        "context window",
    )
    explicit_token_markers = (
        "too many tokens",
        "token limit",
        "maximum token",
    )
    status_or_explicit_markers = (
        "400",
        "413",
        "context_length_exceeded",
        "context_length_exceed",
    )
    has_overflow_phrase = any(marker in message for marker in overflow_phrases)
    has_explicit_token_marker = any(marker in message for marker in explicit_token_markers)
    has_status_or_explicit_marker = any(marker in message for marker in status_or_explicit_markers)
    return has_explicit_token_marker or (has_status_or_explicit_marker and has_overflow_phrase)


def _should_use_chunked_extraction(parsed: parsers.ParsedDocument, max_source_chars: int) -> bool:
    return len(parsed.text) > max_source_chars and bool(parsed.chunks)


def _extract_single_pass(
    *,
    parsed: parsers.ParsedDocument,
    source_text: str,
    client: OllamaClient,
    callbacks: IngestCallbacks,
    thinking_for_extraction: bool,
    db_path: Path,
) -> tuple[Extraction, str]:
    extraction_messages = prompts.build_extraction_messages(parsed.title, source_text, db_path=db_path)
    raw_response = client.chat(
        extraction_messages,
        thinking=thinking_for_extraction,
        json_mode=True,
        temperature=0.3,
    )
    try:
        return _parse_extraction(raw_response), raw_response
    except ValueError as e:
        callbacks.on_extraction_failed(str(e))
        retry_messages = prompts.build_extraction_retry_messages(
            parsed.title,
            source_text,
            raw_response,
            db_path=db_path,
        )
        retry_response = client.chat(
            retry_messages,
            thinking=False,
            json_mode=True,
            temperature=0.2,
        )
        return _parse_extraction(retry_response), retry_response


def _extract_chunked(
    *,
    parsed: parsers.ParsedDocument,
    client: OllamaClient,
    callbacks: IngestCallbacks,
    db_path: Path,
) -> tuple[Extraction, str]:
    chunks = parsed.chunks or [parsed.text]
    total_chunks = len(chunks)
    chunk_results: list[ChunkExtraction] = []
    raw_responses: list[str] = []
    source_slug = slugify.slugify(parsed.title) or "source"

    for chunk_index, chunk_text in enumerate(chunks):
        callbacks.on_chunk_extracting(chunk_index, total_chunks)
        failure_reported = False
        messages = prompts.build_chunk_extraction_messages(
            parsed.title,
            chunk_text,
            chunk_index,
            total_chunks,
            db_path=db_path,
        )
        try:
            raw_response = client.chat(
                messages,
                thinking=False,
                json_mode=True,
                temperature=0.2,
            )
            raw_responses.append(raw_response)
            try:
                chunk_result = _parse_chunk_extraction(raw_response, expected_chunk_index=chunk_index)
            except ValueError as e:
                retry_messages = prompts.build_chunk_extraction_retry_messages(
                    parsed.title,
                    chunk_text,
                    chunk_index,
                    total_chunks,
                    raw_response,
                    db_path=db_path,
                )
                retry_response = client.chat(
                    retry_messages,
                    thinking=False,
                    json_mode=True,
                    temperature=0.2,
                )
                raw_responses.append(retry_response)
                try:
                    chunk_result = _parse_chunk_extraction(retry_response, expected_chunk_index=chunk_index)
                except ValueError as retry_error:
                    callbacks.on_chunk_extraction_failed(chunk_index, total_chunks, str(retry_error))
                    failure_reported = True
                    raise
        except (LLMError, ValueError) as e:
            if not failure_reported:
                callbacks.on_chunk_extraction_failed(chunk_index, total_chunks, str(e))
            raise
        chunk_results.append(chunk_result)
        callbacks.on_chunk_extracted(chunk_result, total_chunks)

    return _aggregate_chunk_extractions(parsed.title, source_slug, chunk_results), "\n\n".join(raw_responses)


def _max_source_chars_for_extraction(config: dict, provider: str | None) -> int:
    """Return the source-text character budget for Pass 1 extraction.

    Local OpenAI-compatible servers (LM Studio, llama.cpp server, etc.) often
    expose smaller context windows than the historical Ollama default.  Keep the
    long Ollama budget for backward compatibility, but default openai-local to a
    safer budget that avoids LM Studio 400 "prompt greater than context length"
    failures. Operators can override via ``ingest.max_source_chars``.
    """
    ingest_cfg = config.get("ingest", {}) if isinstance(config, dict) else {}
    configured = ingest_cfg.get("max_source_chars") if isinstance(ingest_cfg, dict) else None
    try:
        if configured is not None:
            value = int(configured)
            if value > 0:
                return value
    except (TypeError, ValueError):
        pass
    if provider == "openai-local":
        return OPENAI_LOCAL_MAX_SOURCE_CHARS
    return MAX_SOURCE_CHARS


def _logical_prefix(kind: str) -> str:
    return "entities" if kind == "entity" else "concepts"


def _candidate_search_dirs(paths: cfg.WikiPaths, kind: str) -> list[Path]:
    if kind == "entity":
        return [paths.entities, paths.non_categories]
    return [paths.concepts, paths.non_categories]


def _title_for_path(path: Path) -> str:
    parsed = page_writer.read_page(path)
    title = parsed.frontmatter.get("title") if parsed else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    return path.stem.replace("-", " ").strip()


def _exact_slug_candidates(
    kind: str,
    paths: cfg.WikiPaths,
    name: str,
    llm_suggested_slug: str,
) -> list[tuple[str, Path]]:
    candidates: dict[str, Path] = {}
    target_slugs = {
        slugify.slugify(name or ""),
        slugify.slugify(llm_suggested_slug or ""),
    }
    raw_names = {v.strip().casefold() for v in (name, llm_suggested_slug) if v and v.strip()}
    for directory in _candidate_search_dirs(paths, kind):
        if not directory.exists():
            continue
        for page in directory.glob("*.md"):
            title = _title_for_path(page)
            title_slug = slugify.slugify(title)
            title_name = title.strip().casefold()
            if page.stem in target_slugs or title_slug in target_slugs or title_name in raw_names:
                if directory == paths.non_categories:
                    key = f"non_categories/{page.stem}"
                else:
                    key = f"{_logical_prefix(kind)}/{page.stem}"
                candidates[key] = page
    return sorted(candidates.items())


def _resolve_slug(
    name: str,
    kind: str,
    paths: cfg.WikiPaths,
    llm_suggested_slug: str,
) -> ResolutionPlan:
    """Resolve the canonical slug for an entity/concept conservatively."""
    exact_matches = _exact_slug_candidates(kind, paths, name, llm_suggested_slug)
    if len(exact_matches) == 1:
        canonical_slug, final_path = exact_matches[0]
        return ResolutionPlan(
            item=None,  # populated by caller
            kind=kind,
            slug=final_path.stem,
            canonical_slug=canonical_slug,
            action="merge",
            exists=True,
            final_path=final_path,
        )
    if len(exact_matches) > 1:
        raw_slug = slugify.slugify(llm_suggested_slug or name) or "untitled"
        return ResolutionPlan(
            item=None,
            kind=kind,
            slug=raw_slug,
            canonical_slug=f"{_logical_prefix(kind)}/{raw_slug}",
            action="needs_review",
            reason="Multiple exact existing pages matched this candidate.",
        )

    fuzzy = slugify.find_existing_slug(name, kind="any", search_dirs=_candidate_search_dirs(paths, kind))

    raw_slug = llm_suggested_slug or name
    clean = slugify.slugify(raw_slug)
    if not clean:
        clean = slugify.slugify(name) or "untitled"
    if fuzzy:
        return ResolutionPlan(
            item=None,
            kind=kind,
            slug=clean,
            canonical_slug=f"{_logical_prefix(kind)}/{clean}",
            action="needs_review",
            reason=f"Potential existing page '{_logical_prefix(kind)}/{fuzzy}' requires review before merge.",
        )
    return ResolutionPlan(
        item=None,
        kind=kind,
        slug=clean,
        canonical_slug=f"{_logical_prefix(kind)}/{clean}",
        action="create",
    )


def _materialize_resolution_plan(
    item: ExtractedEntity | ExtractedConcept,
    kind: str,
    paths: cfg.WikiPaths,
) -> ResolutionPlan:
    plan = _resolve_slug(item.name, kind, paths, item.slug)
    plan.item = item
    if not plan.final_path and plan.exists:
        plan.final_path = paths.page_dir(_logical_prefix(kind)) / f"{plan.slug}.md"
    return plan


def _resolution_review_candidate(plan: ResolutionPlan) -> ExtractedCandidate:
    return ExtractedCandidate(
        name=plan.item.name,
        slug=plan.slug,
        pageKind="review",
        description=plan.item.description,
        confidence="low",
        reason=plan.reason or "Candidate resolution requires manual review.",
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _build_allowed_links(
    source_slug: str,
    entity_plans: list[ResolutionPlan],
    concept_plans: list[ResolutionPlan],
) -> list[str]:
    allowed = [f"sources/{source_slug}"]
    for plan in [*entity_plans, *concept_plans]:
        if plan.action in {"create", "merge"}:
            allowed.append(plan.canonical_slug)
    return _dedupe_preserve_order(allowed)


def _parse_generated_page(raw: str) -> GeneratedPage:
    json_str = _extract_json_object(raw)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid page JSON from LLM: {e}") from e
    try:
        return GeneratedPage(**data)
    except ValidationError as e:
        raise ValueError(f"Page JSON didn't match expected schema: {e}") from e


def _normalize_link_target(link: str) -> str:
    target = link.strip()
    target = re.sub(r"\.md$", "", target)
    return target.strip(" /")


def _validate_generated_page(
    generated: GeneratedPage,
    *,
    expected_slug: str,
    expected_type: str,
    allowed_links: list[str],
    source_slug: str,
) -> list[str]:
    errors: list[str] = []
    if slugify.slugify(generated.slug) != expected_slug:
        errors.append(f"slug must be '{expected_slug}'")
    if generated.type != expected_type:
        errors.append(f"type must be '{expected_type}'")
    if not generated.body_markdown.strip():
        errors.append("body_markdown must be non-empty")

    body_links = _dedupe_preserve_order(
        [_normalize_link_target(link) for link in page_writer.extract_wikilinks(generated.body_markdown)]
    )
    links_used = _dedupe_preserve_order([_normalize_link_target(link) for link in generated.links_used])
    if body_links != links_used:
        errors.append("links_used must exactly match wikilinks present in body_markdown")

    allowed = {_normalize_link_target(link) for link in allowed_links}
    invalid_links = [link for link in links_used if link not in allowed]
    if invalid_links:
        errors.append(f"links_used contains disallowed links: {', '.join(invalid_links)}")

    required_source = f"sources/{source_slug}.md"
    if required_source not in generated.sources:
        errors.append(f"sources must include '{required_source}'")

    return errors


def _generated_page_to_markdown(
    generated: GeneratedPage,
    *,
    title: str,
    page_type: str,
    tags: list[str],
    today: str,
    source_slug: str,
    existing_page: page_writer.ParsedPage | None,
) -> page_writer.ParsedPage:
    parsed_page = existing_page or page_writer.ParsedPage(frontmatter={}, body="")
    frontmatter = dict(parsed_page.frontmatter)
    frontmatter.setdefault("title", title)
    frontmatter.setdefault("created", today)
    frontmatter["type"] = page_type
    frontmatter.setdefault("tags", tags[:3])
    sources = frontmatter.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    for source in generated.sources:
        if source not in sources:
            sources.append(source)
    required_source = f"sources/{source_slug}.md"
    if required_source not in sources:
        sources.append(required_source)
    frontmatter["sources"] = sources
    frontmatter["updated"] = today
    parsed_page.frontmatter = frontmatter
    parsed_page.body = generated.body_markdown.strip()
    return parsed_page


def _stream_page_response(
    *,
    client: OllamaClient,
    callbacks: IngestCallbacks,
    messages: list[dict[str, str]],
    temperature: float,
) -> str:
    full = ""
    gen = client.chat_stream(messages, thinking=False, temperature=temperature)
    try:
        while True:
            chunk = next(gen)
            try:
                callbacks.on_stream_chunk(chunk)
            except Exception as e:
                raise _StreamCallbackError(str(e)) from e
            full += chunk
    except StopIteration as stop:
        if stop.value:
            full = stop.value
    return full


def _handle_structured_page_failure(
    *,
    plan: ResolutionPlan,
    errors: list[str],
    used_legacy_fallback: bool,
) -> tuple[str | None, bool, list[str]]:
    if plan.exists:
        raise ValueError("; ".join(errors))
    return None, used_legacy_fallback, errors


def _validate_legacy_generated_content(
    *,
    markdown: str,
    expected_slug: str,
    expected_type: str,
    allowed_links: list[str],
    source_slug: str,
) -> tuple[str | None, list[str]]:
    cleaned = page_writer.strip_llm_noise(markdown)
    if not cleaned.strip():
        return None, ["Legacy markdown fallback was empty after cleanup"]

    parsed_page = page_writer.parse_page(cleaned)
    frontmatter = parsed_page.frontmatter or {}
    body_markdown = parsed_page.body.strip()
    body_links = _dedupe_preserve_order(
        [_normalize_link_target(link) for link in page_writer.extract_wikilinks(body_markdown)]
    )

    errors: list[str] = []
    if not frontmatter:
        errors.append("Legacy markdown fallback missing frontmatter")

    page_type = frontmatter.get("type")
    if not isinstance(page_type, str) or not page_type.strip():
        errors.append("Legacy markdown fallback missing frontmatter.type")
        page_type = ""

    sources_value = frontmatter.get("sources")
    if not isinstance(sources_value, list) or not all(isinstance(item, str) for item in sources_value):
        errors.append("Legacy markdown fallback missing valid frontmatter.sources list")
        sources_value = []

    generated = GeneratedPage(
        slug=expected_slug,
        type=page_type,
        body_markdown=body_markdown,
        links_used=body_links,
        sources=sources_value,
    )
    errors.extend(
        _validate_generated_page(
            generated,
            expected_slug=expected_slug,
            expected_type=expected_type,
            allowed_links=allowed_links,
            source_slug=source_slug,
        )
    )
    if errors:
        return None, errors

    return parsed_page.to_markdown(), []


def _build_staged_lint_paths(
    *,
    paths: cfg.WikiPaths,
    staged_files: list[tuple[Path, Path, PageChange]],
) -> tuple[cfg.WikiPaths, set[str], Path]:
    lint_root = Path(tempfile.mkdtemp(prefix="llm-wiki-lint-"))
    lint_paths = cfg.WikiPaths(lint_root)
    page_dir_names = [name for name in paths._page_dirs_config().keys() if name != "assets"]
    raw_dir = lint_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if paths.raw.exists():
        try:
            for entry in paths.raw.rglob("*"):
                if entry.is_file():
                    dest = raw_dir / entry.relative_to(paths.raw)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(entry, dest)
                    except OSError:
                        pass
        except Exception:
            pass
    page_dirs = {name: name for name in page_dir_names}
    config: dict = {
        "paths": {
            "raw_dir": "raw",
            "wiki_dir": ".",
            "page_dirs": page_dirs,
        }
    }
    # Write into the lint staging dir's default config location only. We do not
    # call cfg.save_config because it can be redirected through
    # LLM_WIKI_CONFIG and clobber the project's external runtime config.
    lint_internal = lint_root / ".wiki"
    lint_internal.mkdir(parents=True, exist_ok=True)
    lint_config = lint_internal / "config.yml"
    with lint_config.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)

    for name in page_dir_names:
        src_dir = paths.page_dir(name)
        dest_dir = lint_paths.page_dir(name)
        if src_dir.exists():
            shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)

    changed_paths: set[str] = set()
    for staged, _final, change in staged_files:
        dest = lint_root / change.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, dest)
        changed_paths.add(change.path)

    return lint_paths, changed_paths, lint_root


def _build_review_candidate_page(
    candidate: ExtractedCandidate,
    source_slug: str,
    extraction_tags: list[str],
    today: str,
) -> str:
    """Build deterministic markdown for a review candidate."""
    confidence = candidate.confidence if candidate.confidence is not None else "medium"
    processed_at = _now_iso()

    frontmatter = {
        "title": candidate.name,
        "type": "review",
        "pageKind": "review",
        "status": "pending_review",
        "confidence": confidence,
        "tags": extraction_tags[:3],
        "created": today,
        "updated": today,
        "sources": [f"sources/{source_slug}.md"],
        "source_file": f"sources/{source_slug}.md",
        "processed_at": processed_at,
    }
    if candidate.suggestedExternalOwner:
        frontmatter["suggestedExternalOwner"] = candidate.suggestedExternalOwner
    if candidate.pageKind != "review":
        frontmatter["originalPageKind"] = candidate.pageKind

    body_parts = []
    if candidate.description:
        body_parts.append(candidate.description)
    if candidate.reason:
        body_parts.append(f"**Reason**: {candidate.reason}")
    if candidate.suggestedExternalOwner:
        body_parts.append(f"**Suggested external owner**: `{candidate.suggestedExternalOwner}`")
    body = "\n\n".join(body_parts)

    return page_writer.ParsedPage(frontmatter=frontmatter, body=body).to_markdown()


def _write_review_candidate(
    paths: cfg.WikiPaths,
    candidate: ExtractedCandidate,
    source_slug: str,
    extraction_tags: list[str],
    today: str,
) -> PageChange:
    """Write a review-candidate page to paths.non_categories.

    Review candidates are written directly without an additional LLM call.
    Returns a PageChange for the written file.
    """
    slug = slugify.slugify(candidate.slug or candidate.name) or "untitled-review"
    non_cat_dir = paths.non_categories
    non_cat_dir.mkdir(parents=True, exist_ok=True)
    file_path = non_cat_dir / f"{slug}.md"
    content = _build_review_candidate_page(candidate, source_slug, extraction_tags, today)
    file_path.write_text(content, encoding="utf-8")

    return PageChange(
        slug=slug,
        path=f"non_categories/{slug}.md",
        kind="review",
        operation="created",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _generate_page_content(
    *,
    client: OllamaClient,
    callbacks: IngestCallbacks,
    kind: str,
    plan: ResolutionPlan,
    source_title: str,
    source_slug: str,
    excerpt: str,
    allowed_links: list[str],
    today: str,
    tags: list[str],
    db_path: Path,
) -> tuple[str | None, bool, list[str]]:
    """Return (markdown_content, used_legacy_fallback, validation_errors)."""
    existing_page = page_writer.read_page(plan.final_path) if plan.exists and plan.final_path else None
    existing_content = existing_page.to_markdown() if existing_page else None
    messages = prompts.build_structured_page_messages(
        kind=kind,
        name=plan.item.name,
        slug=plan.slug,
        source_title=source_title,
        source_slug=source_slug,
        description=plan.item.description,
        excerpts=excerpt,
        allowed_links=allowed_links,
        existing_content=existing_content,
        db_path=db_path,
    )

    full = _stream_page_response(
        client=client,
        callbacks=callbacks,
        messages=messages,
        temperature=0.3,
    )

    try:
        generated = _parse_generated_page(full)
    except ValueError as parse_error:
        retry_messages = prompts.build_structured_page_retry_messages(
            kind=kind,
            slug=plan.slug,
            source_slug=source_slug,
            allowed_links=allowed_links,
            bad_response=full,
            validation_errors=[str(parse_error)],
            db_path=db_path,
        )
        retry_full = client.chat(
            retry_messages,
            thinking=False,
            json_mode=True,
            temperature=0.2,
        )
        try:
            generated = _parse_generated_page(retry_full)
        except ValueError as retry_error:
            legacy_content, legacy_errors = _validate_legacy_generated_content(
                markdown=retry_full or full,
                expected_slug=plan.slug,
                expected_type=kind,
                allowed_links=allowed_links,
                source_slug=source_slug,
            )
            if legacy_content is not None:
                return legacy_content, True, []
            return _handle_structured_page_failure(
                plan=plan,
                errors=[f"Structured page JSON parse failed after retry: {retry_error}", *legacy_errors],
                used_legacy_fallback=True,
            )

    validation_errors = _validate_generated_page(
        generated,
        expected_slug=plan.slug,
        expected_type=kind,
        allowed_links=allowed_links,
        source_slug=source_slug,
    )
    if validation_errors:
        retry_messages = prompts.build_structured_page_retry_messages(
            kind=kind,
            slug=plan.slug,
            source_slug=source_slug,
            allowed_links=allowed_links,
            bad_response=full,
            validation_errors=validation_errors,
            db_path=db_path,
        )
        retry_full = client.chat(
            retry_messages,
            thinking=False,
            json_mode=True,
            temperature=0.2,
        )
        try:
            generated = _parse_generated_page(retry_full)
        except ValueError as retry_error:
            return _handle_structured_page_failure(
                plan=plan,
                errors=[f"Structured page retry returned invalid JSON: {retry_error}"],
                used_legacy_fallback=False,
            )
        validation_errors = _validate_generated_page(
            generated,
            expected_slug=plan.slug,
            expected_type=kind,
            allowed_links=allowed_links,
            source_slug=source_slug,
        )
        if validation_errors:
            return _handle_structured_page_failure(
                plan=plan,
                errors=validation_errors,
                used_legacy_fallback=False,
            )

    parsed_page = _generated_page_to_markdown(
        generated,
        title=plan.item.name,
        page_type=kind,
        tags=tags,
        today=today,
        source_slug=source_slug,
        existing_page=existing_page,
    )
    return parsed_page.to_markdown(), False, []


def _lint_changed_pages(paths: cfg.WikiPaths, changed_paths: set[str]) -> list[str]:
    report = lint.run_lint(paths, deep=False, client=None)
    fixable_errors = [
        issue for issue in report.errors
        if issue.fixable and issue.page in changed_paths
    ]
    if fixable_errors:
        lint.apply_fixes(paths, fixable_errors)
        report = lint.run_lint(paths, deep=False, client=None)
    return [issue.page for issue in report.errors if issue.page in changed_paths]


def _stage_review_candidate_file(
    *,
    staging: Path,
    paths: cfg.WikiPaths,
    candidate: ExtractedCandidate,
    source_slug: str,
    tags: list[str],
    today: str,
) -> tuple[Path, Path, PageChange]:
    review_slug = slugify.slugify(candidate.slug or candidate.name) or "untitled-review"
    review_staged = staging / f"non_categories__{review_slug}.md"
    review_final = paths.non_categories / f"{review_slug}.md"
    review_staged.write_text(
        _build_review_candidate_page(candidate, source_slug, tags, today),
        encoding="utf-8",
    )
    return (
        review_staged,
        review_final,
        PageChange(
            slug=review_slug,
            path=f"non_categories/{review_slug}.md",
            kind="review",
            operation="created" if not review_final.exists() else "updated",
        ),
    )


def _mark_source_status(
    paths: cfg.WikiPaths, source_id: int, status: str, last_ingested: str | None = None
) -> None:
    with db.connect(paths.state_db) as conn:
        if last_ingested:
            conn.execute(
                "UPDATE sources SET status = ?, last_ingested = ? WHERE id = ?",
                (status, last_ingested, source_id),
            )
        else:
            conn.execute(
                "UPDATE sources SET status = ? WHERE id = ?", (status, source_id)
            )


def _record_ingest_run(
    paths: cfg.WikiPaths,
    source_id: int,
    started: str,
    mode: str,
    pages_created: int,
    pages_updated: int,
    error: str | None,
) -> None:
    finished = _now_iso()
    with db.connect(paths.state_db) as conn:
        conn.execute(
            """
            INSERT INTO ingest_runs
                (started_at, finished_at, source_id, mode, pages_created,
                 pages_updated, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (started, finished, source_id, mode, pages_created, pages_updated, error),
        )


def _record_source_pages(
    paths: cfg.WikiPaths, source_id: int, changes: list[PageChange], at: str
) -> None:
    with db.connect(paths.state_db) as conn:
        for change in changes:
            conn.execute(
                """
                INSERT INTO source_pages (source_id, wiki_path, operation, at)
                VALUES (?, ?, ?, ?)
                """,
                (source_id, change.path, change.operation, at),
            )


def _auto_discover_pending(paths: cfg.WikiPaths) -> int:
    """Scan raw/ for files not yet tracked in the DB and register them.

    Returns the number of newly discovered files.
    """
    from . import ingest_raw

    with db.connect(paths.state_db) as conn:
        rows = conn.execute("SELECT relpath FROM sources").fetchall()
        tracked = {row["relpath"] for row in rows}

    discovered = 0
    if not paths.raw.exists():
        return 0

    for file_path in paths.raw.rglob("*"):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        if not parsers.is_supported(file_path):
            continue
        try:
            relpath = str(file_path.relative_to(paths.root))
        except ValueError:
            continue
        if relpath in tracked:
            continue
        outcome = ingest_raw.add_file(paths, file_path, copy=False)
        if outcome.result == ingest_raw.AddResult.ADDED:
            discovered += 1
    return discovered


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def ingest_source(
    paths: cfg.WikiPaths,
    source_id: int,
    client: OllamaClient,
    callbacks: IngestCallbacks,
    *,
    mode: str = "interactive",
    thinking_for_extraction: bool = True,
) -> IngestResult:
    """Run the full 3-pass ingest pipeline on a single source."""
    started = _now_iso()

    # 1. Load the source row
    with db.connect(paths.state_db) as conn:
        row = conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if row is None:
            result = IngestResult(
                source_id=source_id,
                source_title="?",
                source_slug="?",
                error=f"No source with id {source_id}",
            )
            callbacks.on_error(result.error)
            return result
        source_row = dict(row)

    file_path = paths.root / source_row["relpath"]
    callbacks.on_start(source_id, source_row["relpath"], str(file_path))

    # 2. Parse the source
    callbacks.on_parsing()
    try:
        # Load chunk size and overlap from settings or use defaults
        config = cfg.load_config(paths)
        chunk_size = config.get("chunking", {}).get("chunk_size", 1500)
        overlap = config.get("chunking", {}).get("overlap", 200)
        parsed = parsers.parse(file_path, chunk_size=chunk_size, overlap=overlap)
    except parsers.ParserError as e:
        result = IngestResult(
            source_id=source_id,
            source_title=source_row["relpath"],
            source_slug="?",
            error=f"Parse failed: {e}",
        )
        _mark_source_status(paths, source_id, "error")
        _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
        callbacks.on_error(result.error)
        _record_ingest_log(paths, source_id, "failure", error_message=result.error)
        return result

    # 3. Pass 1 — extraction
    callbacks.on_extracting()
    max_source_chars = _max_source_chars_for_extraction(config, client.provider)
    use_chunked_extraction = _should_use_chunked_extraction(parsed, max_source_chars)
    raw_response: str | None = None
    try:
        if use_chunked_extraction:
            extraction, raw_response = _extract_chunked(
                parsed=parsed,
                client=client,
                callbacks=callbacks,
                db_path=paths.state_db,
            )
        else:
            extraction, raw_response = _extract_single_pass(
                parsed=parsed,
                source_text=parsed.text,
                client=client,
                callbacks=callbacks,
                thinking_for_extraction=thinking_for_extraction,
                db_path=paths.state_db,
            )
    except (OllamaNotRunning, ModelNotFound) as e:
        result = IngestResult(
            source_id=source_id,
            source_title=parsed.title,
            source_slug="?",
            error=str(e),
        )
        callbacks.on_error(result.error)
        # Don't mark as error — user needs to fix Ollama, then retry
        _record_ingest_log(paths, source_id, "failure", error_message=result.error)
        return result
    except LLMError as e:
        if not use_chunked_extraction and parsed.chunks and _is_context_overflow_error(e):
            try:
                extraction, raw_response = _extract_chunked(
                    parsed=parsed,
                    client=client,
                    callbacks=callbacks,
                    db_path=paths.state_db,
                )
            except (LLMError, ValueError) as e2:
                result = IngestResult(
                    source_id=source_id,
                    source_title=parsed.title,
                    source_slug="?",
                    error=f"Extraction failed after chunked fallback: {e2}",
                )
                _mark_source_status(paths, source_id, "error")
                _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
                callbacks.on_error(result.error)
                _record_ingest_log(paths, source_id, "failure", error_message=result.error)
                return result
        else:
            result = IngestResult(
                source_id=source_id,
                source_title=parsed.title,
                source_slug="?",
                error=f"LLM error: {e}",
            )
            _mark_source_status(paths, source_id, "error")
            _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
            callbacks.on_error(result.error)
            _record_ingest_log(paths, source_id, "failure", error_message=result.error)
            return result
    except ValueError as e:
        result = IngestResult(
            source_id=source_id,
            source_title=parsed.title,
            source_slug="?",
            error=f"Extraction failed after retry: {e}",
        )
        _mark_source_status(paths, source_id, "error")
        _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
        callbacks.on_error(result.error)
        _record_ingest_log(paths, source_id, "failure", error_message=result.error, raw_response=raw_response)
        return result

    # Sanitize the source slug
    source_slug = slugify.slugify(extraction.source_slug or extraction.title)
    extraction.source_slug = source_slug

    callbacks.on_extracted(extraction)

    # 4. Interactive confirmation gate
    if mode == "interactive":
        if not callbacks.ask_confirm(extraction):
            result = IngestResult(
                source_id=source_id,
                source_title=parsed.title,
                source_slug=source_slug,
                skipped=True,
            )
            callbacks.on_complete(result)
            return result

    # 5. Resolve slugs for all entities and concepts conservatively
    today = page_writer.today_iso()
    entity_plans: list[ResolutionPlan] = []
    for ent in extraction.entities:
        entity_plans.append(_materialize_resolution_plan(ent, "entity", paths))

    concept_plans: list[ResolutionPlan] = []
    for con in extraction.concepts:
        concept_plans.append(_materialize_resolution_plan(con, "concept", paths))

    # 5b. Collect review candidates. They are staged with other pages below so
    # ingest remains transactional until finalization.
    review_candidates = [cand for cand in extraction.candidates if cand.pageKind == "review"]
    review_candidates.extend(_resolution_review_candidate(plan) for plan in entity_plans if plan.action == "needs_review")
    review_candidates.extend(_resolution_review_candidate(plan) for plan in concept_plans if plan.action == "needs_review")
    actionable_entity_plans = [plan for plan in entity_plans if plan.action in {"create", "merge"}]
    actionable_concept_plans = [plan for plan in concept_plans if plan.action in {"create", "merge"}]
    base_allowed_links = _build_allowed_links(source_slug, actionable_entity_plans, actionable_concept_plans)

    # 6. Staging directory for transactional writes
    staging = Path(tempfile.mkdtemp(prefix="llm-wiki-ingest-"))
    try:
        staged_files: list[tuple[Path, Path, PageChange]] = []  # (staged, final, change)

        for cand in review_candidates:
            staged_files.append(
                _stage_review_candidate_file(
                    staging=staging,
                    paths=paths,
                    candidate=cand,
                    source_slug=source_slug,
                    tags=extraction.tags,
                    today=today,
                )
            )

        # 6a. Build the "related" list for each page (used in draft prompts)
        all_entity_slugs = [plan.canonical_slug for plan in actionable_entity_plans]
        all_concept_slugs = [plan.canonical_slug for plan in actionable_concept_plans]

        def _related_for(exclude_slug: str, exclude_kind: str) -> list[str]:
            rel: list[str] = []
            for s in all_entity_slugs:
                if not (exclude_kind == "entity" and s == exclude_slug):
                    rel.append(s)
            for s in all_concept_slugs:
                if not (exclude_kind == "concept" and s == exclude_slug):
                    rel.append(s)
            return rel

        excerpt = _build_excerpt(parsed.text)

        # 6b. Draft/merge each entity page
        for plan in actionable_entity_plans:
            ent = plan.item
            slug = plan.slug
            exists = plan.exists
            operation = "updated" if exists else "created"
            callbacks.on_drafting_page("entity", slug, operation)

            # Resolve actual final path (checking standard and non_categories)
            final_path = plan.final_path or (paths.entities / f"{slug}.md")
            if not plan.final_path and not final_path.exists():
                non_cat_path = paths.non_categories / f"{slug}.md"
                if non_cat_path.exists():
                    final_path = non_cat_path

            # Initially staged as entities, but we may change it to non_categories based on confidence
            staged_path = staging / f"entities__{slug}.md"

            try:
                content, _, validation_errors = _generate_page_content(
                    client=client,
                    callbacks=callbacks,
                    kind="entity",
                    plan=plan,
                    source_title=parsed.title,
                    source_slug=source_slug,
                    excerpt=excerpt,
                    allowed_links=_dedupe_preserve_order([link for link in base_allowed_links if link == f"sources/{source_slug}" or link == plan.canonical_slug or link in _related_for(plan.canonical_slug, "entity")]),
                    today=today,
                    tags=extraction.tags,
                    db_path=paths.state_db,
                )
                if content is None:
                    reason = "; ".join(validation_errors) or "Structured page validation failed"
                    review_candidate = ExtractedCandidate(
                        name=ent.name,
                        slug=slug,
                        pageKind="review",
                        description=ent.description,
                        confidence="low",
                        reason=reason,
                    )
                    staged, final, change = _stage_review_candidate_file(
                        staging=staging,
                        paths=paths,
                        candidate=review_candidate,
                        source_slug=source_slug,
                        tags=extraction.tags,
                        today=today,
                    )
                    staged_files.append((staged, final, change))
                    callbacks.on_page_written(change)
                    continue

                parsed_page = page_writer.parse_page(content)
                if not parsed_page.frontmatter:
                    # LLM forgot frontmatter — synthesize minimal one
                    parsed_page.frontmatter = {
                        "title": ent.name,
                        "type": "entity",
                        "tags": extraction.tags[:3],
                        "created": today,
                        "updated": today,
                        "sources": [f"sources/{source_slug}.md"],
                        "confidence": "medium",
                    }
                    parsed_page.body = page_writer.strip_llm_noise(content)
                
                # Determine classification confidence and folder
                raw_conf = parsed_page.frontmatter.get("confidence", "medium")
                confidence_val = raw_conf
                try:
                    confidence_val = float(raw_conf)
                except (ValueError, TypeError):
                    pass
                
                is_low_confidence = False
                if isinstance(confidence_val, float):
                    if confidence_val < 0.70:
                        is_low_confidence = True
                elif isinstance(confidence_val, str):
                    if confidence_val.lower() in ("low", "ambiguous", "pending"):
                        is_low_confidence = True
                
                status = "approved"
                folder = "entities"
                if is_low_confidence:
                    status = "pending_review"
                    folder = "non_categories"
                
                if exists:
                    folder = final_path.parent.name
                    if folder == "non_categories":
                        status = "pending_review"
                else:
                    final_path = paths.page_dir(folder) / f"{slug}.md"
                    staged_path = staging / f"{folder}__{slug}.md"

                # Always ensure source is in sources list
                page_writer.add_source_to_frontmatter(parsed_page, source_slug, today)

                # Update frontmatter fields
                processed_at = _now_iso()
                page_writer.prepare_page_frontmatter(
                    parsed_page,
                    status=status,
                    confidence=confidence_val,
                    processed_at=processed_at,
                    source_file=f"sources/{source_slug}.md",
                )

                content = parsed_page.to_markdown()
                staged_path.write_text(content, encoding="utf-8")
                change = PageChange(
                    slug=slug,
                    path=f"{folder}/{slug}.md",
                    kind="entity",
                    operation=operation,
                )
                staged_files.append((staged_path, final_path, change))
                callbacks.on_page_written(change)

            except (LLMError, ValueError) as e:
                if isinstance(e, _StreamCallbackError):
                    result = IngestResult(
                        source_id=source_id,
                        source_title=parsed.title,
                        source_slug=source_slug,
                        error=f"Failed drafting entity '{slug}': {e}",
                    )
                    _mark_source_status(paths, source_id, "error")
                    _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
                    callbacks.on_error(result.error)
                    _record_ingest_log(paths, source_id, "failure", error_message=result.error)
                    return result
                if not exists:
                    review_candidate = ExtractedCandidate(
                        name=ent.name,
                        slug=slug,
                        pageKind="review",
                        description=ent.description,
                        confidence="low",
                        reason=str(e),
                    )
                    staged, final, change = _stage_review_candidate_file(
                        staging=staging,
                        paths=paths,
                        candidate=review_candidate,
                        source_slug=source_slug,
                        tags=extraction.tags,
                        today=today,
                    )
                    staged_files.append((staged, final, change))
                    callbacks.on_page_written(change)
                    continue
                result = IngestResult(
                    source_id=source_id,
                    source_title=parsed.title,
                    source_slug=source_slug,
                    error=f"Failed drafting entity '{slug}': {e}",
                )
                _mark_source_status(paths, source_id, "error")
                _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
                callbacks.on_error(result.error)
                _record_ingest_log(paths, source_id, "failure", error_message=result.error)
                return result

        # 6c. Draft/merge each concept page
        for plan in actionable_concept_plans:
            con = plan.item
            slug = plan.slug
            exists = plan.exists
            operation = "updated" if exists else "created"
            callbacks.on_drafting_page("concept", slug, operation)

            # Resolve actual final path (checking standard and non_categories)
            final_path = plan.final_path or (paths.concepts / f"{slug}.md")
            if not plan.final_path and not final_path.exists():
                non_cat_path = paths.non_categories / f"{slug}.md"
                if non_cat_path.exists():
                    final_path = non_cat_path

            staged_path = staging / f"concepts__{slug}.md"

            try:
                content, _, validation_errors = _generate_page_content(
                    client=client,
                    callbacks=callbacks,
                    kind="concept",
                    plan=plan,
                    source_title=parsed.title,
                    source_slug=source_slug,
                    excerpt=excerpt,
                    allowed_links=_dedupe_preserve_order([link for link in base_allowed_links if link == f"sources/{source_slug}" or link == plan.canonical_slug or link in _related_for(plan.canonical_slug, "concept")]),
                    today=today,
                    tags=extraction.tags,
                    db_path=paths.state_db,
                )
                if content is None:
                    reason = "; ".join(validation_errors) or "Structured page validation failed"
                    review_candidate = ExtractedCandidate(
                        name=con.name,
                        slug=slug,
                        pageKind="review",
                        description=con.description,
                        confidence="low",
                        reason=reason,
                    )
                    staged, final, change = _stage_review_candidate_file(
                        staging=staging,
                        paths=paths,
                        candidate=review_candidate,
                        source_slug=source_slug,
                        tags=extraction.tags,
                        today=today,
                    )
                    staged_files.append((staged, final, change))
                    callbacks.on_page_written(change)
                    continue

                parsed_page = page_writer.parse_page(content)
                if not parsed_page.frontmatter:
                    parsed_page.frontmatter = {
                        "title": con.name,
                        "type": "concept",
                        "tags": extraction.tags[:3],
                        "created": today,
                        "updated": today,
                        "sources": [f"sources/{source_slug}.md"],
                        "confidence": "medium",
                    }
                    parsed_page.body = page_writer.strip_llm_noise(content)
                
                # Determine classification confidence and folder
                raw_conf = parsed_page.frontmatter.get("confidence", "medium")
                confidence_val = raw_conf
                try:
                    confidence_val = float(raw_conf)
                except (ValueError, TypeError):
                    pass
                
                is_low_confidence = False
                if isinstance(confidence_val, float):
                    if confidence_val < 0.70:
                        is_low_confidence = True
                elif isinstance(confidence_val, str):
                    if confidence_val.lower() in ("low", "ambiguous", "pending"):
                        is_low_confidence = True
                
                status = "approved"
                folder = "concepts"
                if is_low_confidence:
                    status = "pending_review"
                    folder = "non_categories"
                
                if exists:
                    folder = final_path.parent.name
                    if folder == "non_categories":
                        status = "pending_review"
                else:
                    final_path = paths.page_dir(folder) / f"{slug}.md"
                    staged_path = staging / f"{folder}__{slug}.md"

                # Always ensure source is in sources list
                page_writer.add_source_to_frontmatter(parsed_page, source_slug, today)

                # Update frontmatter fields
                processed_at = _now_iso()
                page_writer.prepare_page_frontmatter(
                    parsed_page,
                    status=status,
                    confidence=confidence_val,
                    processed_at=processed_at,
                    source_file=f"sources/{source_slug}.md",
                )

                content = parsed_page.to_markdown()
                staged_path.write_text(content, encoding="utf-8")
                change = PageChange(
                    slug=slug,
                    path=f"{folder}/{slug}.md",
                    kind="concept",
                    operation=operation,
                )
                staged_files.append((staged_path, final_path, change))
                callbacks.on_page_written(change)

            except (LLMError, ValueError) as e:
                if isinstance(e, _StreamCallbackError):
                    result = IngestResult(
                        source_id=source_id,
                        source_title=parsed.title,
                        source_slug=source_slug,
                        error=f"Failed drafting concept '{slug}': {e}",
                    )
                    _mark_source_status(paths, source_id, "error")
                    _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
                    callbacks.on_error(result.error)
                    _record_ingest_log(paths, source_id, "failure", error_message=result.error)
                    return result
                if not exists:
                    review_candidate = ExtractedCandidate(
                        name=con.name,
                        slug=slug,
                        pageKind="review",
                        description=con.description,
                        confidence="low",
                        reason=str(e),
                    )
                    staged, final, change = _stage_review_candidate_file(
                        staging=staging,
                        paths=paths,
                        candidate=review_candidate,
                        source_slug=source_slug,
                        tags=extraction.tags,
                        today=today,
                    )
                    staged_files.append((staged, final, change))
                    callbacks.on_page_written(change)
                    continue
                result = IngestResult(
                    source_id=source_id,
                    source_title=parsed.title,
                    source_slug=source_slug,
                    error=f"Failed drafting concept '{slug}': {e}",
                )
                _mark_source_status(paths, source_id, "error")
                _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
                callbacks.on_error(result.error)
                _record_ingest_log(paths, source_id, "failure", error_message=result.error)
                return result

        # 6d. Pass 3 — source summary page
        callbacks.on_drafting_page("source", source_slug, "created")
        source_final = paths.sources / f"{source_slug}.md"
        source_staged = staging / f"sources__{source_slug}.md"

        try:
            download_url = f"/api/raw-download/{source_id}"
            messages = prompts.build_source_page_messages(
                source_title=parsed.title,
                source_slug=source_slug,
                file_path=download_url,
                file_type=parsed.file_type,
                summary=extraction.summary,
                key_takeaways=extraction.key_takeaways,
                tags=extraction.tags,
                entity_slugs=[plan.slug for plan in actionable_entity_plans],
                concept_slugs=[plan.slug for plan in actionable_concept_plans],
                today=today,
                db_path=paths.state_db,
            )

            full = _stream_page_response(
                client=client,
                callbacks=callbacks,
                messages=messages,
                temperature=0.3,
            )

            content = page_writer.strip_llm_noise(full)
            
            # Replace local path mentions with download link
            local_path_str = source_row["relpath"]
            if local_path_str in content:
                content = content.replace(local_path_str, f"[Download Original file]({download_url})")

            parsed_page = page_writer.parse_page(content)
            if not parsed_page.frontmatter:
                parsed_page.frontmatter = {
                    "title": parsed.title,
                    "type": "source",
                    "tags": extraction.tags,
                    "created": today,
                    "updated": today,
                    "file_path": source_row["relpath"],
                    "file_type": parsed.file_type,
                }
                parsed_page.body = content
            content = parsed_page.to_markdown()

            source_staged.write_text(content, encoding="utf-8")
            source_operation = "updated" if source_final.exists() else "created"
            change = PageChange(
                slug=source_slug,
                path=f"sources/{source_slug}.md",
                kind="source",
                operation=source_operation,
            )
            staged_files.append((source_staged, source_final, change))
            callbacks.on_page_written(change)

        except LLMError as e:
            result = IngestResult(
                source_id=source_id,
                source_title=parsed.title,
                source_slug=source_slug,
                error=f"Failed drafting source page: {e}",
            )
            _mark_source_status(paths, source_id, "error")
            _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
            callbacks.on_error(result.error)
            _record_ingest_log(paths, source_id, "failure", error_message=result.error)
            return result

        # 7. Lint staged files before commit
        callbacks.on_finalizing()
        lint_paths, changed_paths, lint_root = _build_staged_lint_paths(
            paths=paths,
            staged_files=staged_files,
        )
        try:
            lint_error_pages = _lint_changed_pages(lint_paths, changed_paths)
        finally:
            shutil.rmtree(lint_root, ignore_errors=True)

        if lint_error_pages:
            result = IngestResult(
                source_id=source_id,
                source_title=parsed.title,
                source_slug=source_slug,
                error=(
                    "Lint errors remain on staged pages after auto-fix: "
                    + ", ".join(sorted(lint_error_pages))
                ),
            )
            _mark_source_status(paths, source_id, "error")
            _record_ingest_run(paths, source_id, started, mode, 0, 0, result.error)
            callbacks.on_error(result.error)
            _record_ingest_log(paths, source_id, "failure", error_message=result.error, raw_response=raw_response)
            return result

        # 8. Commit: move staged files to final locations
        pages_created = 0
        pages_updated = 0
        changes: list[PageChange] = []
        for staged, final, change in staged_files:
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, final)
            changes.append(change)
            if change.operation == "created":
                pages_created += 1
            else:
                pages_updated += 1

        # Review candidates are part of staged_files, so they are committed
        # atomically with source/entity/concept pages above.

        # 9. Rebuild index.md and append to log.md
        page_writer.rebuild_index(paths, today)
        log_bullets = [
            f"{c.operation}: [[{c.path.replace('.md', '')}]]" for c in changes
        ]
        page_writer.append_log_entry(
            paths, today, "ingest", parsed.title, log_bullets
        )

        # 10. Record in DB
        _record_source_pages(paths, source_id, changes, _now_iso())
        _mark_source_status(paths, source_id, "ingested", last_ingested=_now_iso())
        _record_ingest_run(
            paths,
            source_id,
            started,
            mode,
            pages_created,
            pages_updated,
            error=None,
        )
        _record_ingest_log(paths, source_id, "success", raw_response=raw_response)

        result = IngestResult(
            source_id=source_id,
            source_title=parsed.title,
            source_slug=source_slug,
            pages_created=pages_created,
            pages_updated=pages_updated,
            changes=changes,
        )
        callbacks.on_complete(result)
        return result

    finally:
        shutil.rmtree(staging, ignore_errors=True)


def ingest_pending(
    paths: cfg.WikiPaths,
    client: OllamaClient,
    callbacks_factory: Callable[[], IngestCallbacks],
    *,
    mode: str = "interactive",
    auto_discover: bool = True,
    thinking_for_extraction: bool = True,
) -> list[IngestResult]:
    """Ingest all pending sources in the DB.

    Args:
        paths: Wiki project paths.
        client: An active Ollama client.
        callbacks_factory: Called once per source to get a fresh callback object.
        mode: 'interactive' | 'batch'.
        auto_discover: If True, scan raw/ for untracked files first.
        thinking_for_extraction: Whether to use Qwen3's thinking mode in Pass 1.

    Returns:
        A list of IngestResult, one per source attempted.
    """
    if auto_discover:
        _auto_discover_pending(paths)

    with db.connect(paths.state_db) as conn:
        rows = conn.execute(
            "SELECT id FROM sources WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()
        pending_ids = [row["id"] for row in rows]

    results: list[IngestResult] = []
    for sid in pending_ids:
        cb = callbacks_factory()
        result = ingest_source(
            paths,
            sid,
            client,
            cb,
            mode=mode,
            thinking_for_extraction=thinking_for_extraction,
        )
        results.append(result)
        if result.error and "Ollama" in result.error:
            # Stop the batch if Ollama is unreachable — no point continuing
            break

    return results


def _get_active_prompt_version(db_path: Path, prompt_key: str = "extract") -> str:
    import sqlite3
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT version_tag FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
                (prompt_key,)
            ).fetchone()
            if row:
                return row["version_tag"]
    except Exception:
        pass
    return "v1.0"


def _record_ingest_log(
    paths: cfg.WikiPaths,
    source_id: int,
    status: str,
    error_message: str | None = None,
    raw_response: str | None = None,
):
    import sqlite3
    processed_at = _now_iso()
    prompt_ver = _get_active_prompt_version(paths.state_db, "extract")
    try:
        with sqlite3.connect(paths.state_db) as conn:
            conn.execute(
                """
                INSERT INTO ingest_logs (source_id, prompt_version, status, error_message, raw_response, processed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_id, prompt_ver, status, error_message, raw_response, processed_at)
            )
            conn.commit()
    except Exception:
        pass
