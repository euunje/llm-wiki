from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llm_wiki.common import new_id
from llm_wiki.llm.chat import call_json_task
from llm_wiki.pipeline.section_chunking import SectionChunk
from llm_wiki.pipeline.wiki_extract import build_chunk_prompt_text, extract_wiki_page_candidates
from llm_wiki.schema.prompts import DEFAULT_PROMPTS, get_active_prompt
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate, validate_wiki_page_candidate
from llm_wiki.workspace import WorkspacePaths


@dataclass
class LLMPageCandidateAttempt:
    attempted: bool = False
    status: str = "not_attempted"
    retry_reason: str | None = None
    json_repair_applied: bool = False
    fallback_used: bool = False
    error: dict[str, object] | None = None
    validation_errors: dict[str, list[str]] = field(default_factory=dict)
    http_response_size_bytes: int | None = None
    api_key_present: bool | None = None
    content_preview: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "status": self.status,
            "retry_reason": self.retry_reason,
            "json_repair_applied": self.json_repair_applied,
            "fallback_used": self.fallback_used,
            "error": self.error,
            "validation_errors": self.validation_errors,
            "http_response_size_bytes": self.http_response_size_bytes,
            "api_key_present": self.api_key_present,
            "content_preview": self.content_preview,
        }


def extract_wiki_page_candidates_with_optional_llm(
    workspace: WorkspacePaths,
    *,
    source_id: str,
    source_title: str,
    chunks: list[SectionChunk],
    use_llm: bool,
) -> tuple[list[WikiPageCandidate], list[dict[str, object]], LLMPageCandidateAttempt]:
    if not use_llm:
        candidates, claims_log = extract_wiki_page_candidates(source_id, source_title, chunks)
        return candidates, claims_log, LLMPageCandidateAttempt()

    attempt = LLMPageCandidateAttempt(attempted=True, status="attempted")
    system_prompt = _active_prompt_text(workspace, "wiki_page_candidates_initial")
    initial_prompt = _initial_user_prompt(source_id, source_title, chunks)
    try:
        result = call_json_task(
            workspace,
            model_id="chat_default",
            system_prompt=system_prompt,
            user_prompt=initial_prompt,
        )
        candidates, errors = _candidates_from_llm_json(result.get("parsed_json"), source_id, chunks)
        _record_attempt_result(attempt, result)
        if candidates and not errors:
            attempt.status = "parsed"
            return candidates, _claims_log(candidates), attempt
        attempt.validation_errors = errors or {"candidates": ["empty_candidates"]}
        retry_reason = "schema_validation_failed" if errors else "empty_candidates"
        retry_prompt = _retry_user_prompt(
            workspace=workspace,
            source_id=source_id,
            source_title=source_title,
            chunks=chunks,
            raw_response=str(result.get("content") or ""),
            reason=retry_reason,
            validation_errors=attempt.validation_errors,
        )
    except Exception as exc:
        attempt.error = {"type": exc.__class__.__name__, "reason": str(exc)}
        retry_reason = "parse_failed"
        raw_response = str(getattr(exc, "content", "") or "")
        retry_prompt = _retry_user_prompt(
            workspace=workspace,
            source_id=source_id,
            source_title=source_title,
            chunks=chunks,
            raw_response=raw_response,
            reason=retry_reason,
            parse_error=str(exc),
        )

    try:
        retry_result = call_json_task(
            workspace,
            model_id="chat_default",
            system_prompt=system_prompt,
            user_prompt=retry_prompt,
        )
        retry_candidates, retry_errors = _candidates_from_llm_json(retry_result.get("parsed_json"), source_id, chunks)
        _record_attempt_result(attempt, retry_result)
        attempt.retry_reason = retry_reason
        if retry_candidates and not retry_errors:
            attempt.status = "retried"
            return retry_candidates, _claims_log(retry_candidates), attempt
        attempt.status = "fallback"
        attempt.fallback_used = True
        attempt.validation_errors = retry_errors or {"candidates": ["empty_candidates_after_retry"]}
    except Exception as exc:
        attempt.status = "fallback"
        attempt.fallback_used = True
        attempt.retry_reason = retry_reason
        attempt.error = {"type": exc.__class__.__name__, "reason": str(exc)}

    fallback_candidates, fallback_claims = extract_wiki_page_candidates(source_id, source_title, chunks)
    return fallback_candidates, fallback_claims, attempt


def _record_attempt_result(attempt: LLMPageCandidateAttempt, result: dict[str, Any]) -> None:
    attempt.json_repair_applied = attempt.json_repair_applied or bool(result.get("json_repair_applied"))
    if result.get("http_response_size_bytes") is not None:
        attempt.http_response_size_bytes = int(result.get("http_response_size_bytes") or 0)
    if result.get("api_key_present") is not None:
        attempt.api_key_present = bool(result.get("api_key_present"))
    attempt.content_preview = str(result.get("content") or "")[:600]


def _active_prompt_text(workspace: WorkspacePaths, task_type: str) -> str:
    try:
        row = get_active_prompt(workspace.db, task_type)
        text = str(row.get("prompt_text") or "").strip()
        if text:
            return text
    except Exception:
        pass
    return str(DEFAULT_PROMPTS.get(task_type) or "").strip() or _system_prompt()


def _system_prompt() -> str:
    return DEFAULT_PROMPTS["wiki_page_candidates_initial"]


def _initial_user_prompt(source_id: str, source_title: str, chunks: list[SectionChunk]) -> str:
    return (
        f"SOURCE_ID: {source_id}\n"
        f"SOURCE_TITLE: {source_title}\n\n"
        "Return JSON schema:\n"
        "{\"document_type\":\"spec|reference|manual|protocol|API|structured_guide|short_readme|announcement|single_tool_overview|essay|analysis|benchmark|comparison\",\"target_candidate_count\":int,\"candidates\":[{\"title\":str,\"summary\":str,\"node_type\":\"concept\",\"tags\":[\"concept\", str],\"draft_body\":str,\"aliases\":[str]?}]}\n"
        "Rules: every candidate must have non-empty summary/tags/draft_body, and tags must include the lowercase node_type value such as 'concept'.\n"
        "Granularity: first classify document_type, then choose candidate count from that type's target range before writing candidates. Ranges: spec/reference/manual/protocol/API/structured_guide -> 6-12 durable section-level concept pages when enough distinct sections exist; short_readme/announcement/single_tool_overview -> 1-4 pages; essay/analysis/benchmark/comparison -> 3-6 pages. Treat the range as your planning target, not a vague suggestion. If you choose fewer than the range for a structured source, the supplied chunks must genuinely lack enough distinct durable concepts. Do not force unsupported pages, but do not collapse clearly distinct durable concepts.\n\n"
        "SOURCE CHUNKS:\n"
        f"{build_chunk_prompt_text(_prompt_chunks(chunks), max_chars=5000)}"
    )


def _retry_user_prompt(
    *,
    workspace: WorkspacePaths,
    source_id: str,
    source_title: str,
    chunks: list[SectionChunk],
    raw_response: str,
    reason: str,
    parse_error: str | None = None,
    validation_errors: dict[str, list[str]] | None = None,
) -> str:
    retry_task_type = f"wiki_page_candidates_retry_{reason}"
    correction_prompt = _active_prompt_text(workspace, retry_task_type)
    return (
        f"{correction_prompt}\n\n"
        f"Your previous page candidate JSON failed with reason: {reason}.\n"
        f"SOURCE_ID: {source_id}\nSOURCE_TITLE: {source_title}\n"
        f"Parse error: {parse_error or 'none'}\n"
        f"Validation errors: {json.dumps(validation_errors or {}, ensure_ascii=False, sort_keys=True)}\n\n"
        "Raw response follows. Correct it; do not add prose. Return ONLY valid JSON matching this schema:\n"
        "{\"document_type\":str,\"target_candidate_count\":int,\"candidates\":[{\"title\":str,\"summary\":non_empty_str,\"node_type\":\"concept\",\"tags\":[\"concept\", non_empty_str],\"draft_body\":non_empty_str,\"aliases\":[str]?}]}\n\n"
        f"RAW RESPONSE:\n{raw_response}\n\n"
        "SOURCE CHUNKS:\n"
        f"{build_chunk_prompt_text(_prompt_chunks(chunks), max_chars=3500)}"
    )


def _prompt_chunks(chunks: list[SectionChunk]) -> list[dict[str, object]]:
    return [
        {
            "text": chunk.text,
            "locator": {"heading_path": list(chunk.heading_path)},
        }
        for chunk in chunks[:8]
    ]


def _candidates_from_llm_json(payload: object, source_id: str, chunks: list[SectionChunk]) -> tuple[list[WikiPageCandidate], dict[str, list[str]]]:
    normalized = _normalize_payload(payload)
    raw_candidates = normalized.get("candidates") if isinstance(normalized, dict) else None
    if not isinstance(raw_candidates, list) or not raw_candidates:
        return [], {"candidates": ["empty_candidates"]}
    candidates: list[WikiPageCandidate] = []
    errors: dict[str, list[str]] = {}
    default_ref = _default_section_ref(source_id, chunks)
    default_claim_chunk = chunks[0] if chunks else None
    for index, item in enumerate(raw_candidates):
        key = f"candidate_{index}"
        if not isinstance(item, dict):
            errors[key] = ["candidate must be an object"]
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        draft_body = str(item.get("draft_body") or item.get("body") or item.get("content") or "").strip()
        tags = _string_list(item.get("tags") or item.get("keywords"))
        aliases = _string_list(item.get("aliases"))
        candidate = WikiPageCandidate(
            candidate_key=str(item.get("candidate_key") or new_id("page")),
            node_type=str(item.get("node_type") or "concept").strip() or "concept",
            title=title,
            summary=summary,
            source_id=source_id,
            aliases=aliases,
            keywords=_string_list(item.get("keywords")) or tags,
            tags=tags,
            body_outline=["Definition", "Source evidence"],
            draft_body=draft_body,
            source_section_refs=[default_ref] if default_ref else [],
            evidence_claims=[_default_claim(source_id, summary or title, default_claim_chunk)] if default_claim_chunk else [],
        )
        candidate_errors = validate_wiki_page_candidate(candidate)
        if candidate_errors:
            errors[key] = candidate_errors
            continue
        candidates.append(candidate)
    return candidates, errors


def _normalize_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    if "candidates" in payload:
        return payload
    for alias in ("pages", "wiki_pages", "page_candidates"):
        if alias in payload:
            return {"candidates": payload.get(alias)}
    return payload


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _default_section_ref(source_id: str, chunks: list[SectionChunk]) -> SourceSectionRef | None:
    if not chunks:
        return None
    chunk = chunks[0]
    return SourceSectionRef(
        chunk_id=f"chunk_{source_id}_{chunk.chunk_index:03d}",
        heading_path=chunk.heading_path,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )


def _default_claim(source_id: str, statement: str, chunk: SectionChunk | None) -> EvidenceClaim:
    assert chunk is not None
    text = chunk.text.strip()
    quote = text[:280] or statement
    return EvidenceClaim(
        claim_id=new_id("claim"),
        statement=statement or "LLM generated page candidate.",
        source_id=source_id,
        chunk_id=f"chunk_{source_id}_{chunk.chunk_index:03d}",
        quote=quote,
        char_start=chunk.char_start,
        char_end=min(chunk.char_end, chunk.char_start + len(quote)),
    )


def _claims_log(candidates: list[WikiPageCandidate]) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    for candidate in candidates:
        for claim in candidate.evidence_claims:
            claims.append(
                {
                    "claim_id": claim.claim_id,
                    "source_id": claim.source_id,
                    "chunk_id": claim.chunk_id,
                    "statement": claim.statement,
                    "quote": claim.quote,
                    "char_start": claim.char_start,
                    "char_end": claim.char_end,
                    "llm_page_candidate": True,
                }
            )
    return claims
