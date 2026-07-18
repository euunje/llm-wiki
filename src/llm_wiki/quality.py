"""Phase 2 rubric checks for summaries, titles, mappings, and language policy."""

from __future__ import annotations

import re
from typing import Any

TECH_TERMS = {
    "RAG", "LLM", "OpenCode", "Claude Code", "Palantir", "SpaceX", "embedding",
    "ontology", "token", "API", "PDF", "HTML", "Markdown", "ILM", "SPEC",
}

HANGUL_RE = re.compile(r"[가-힣]")
LATIN_TECH_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+.#/-]*(?:\s+[A-Z][A-Za-z0-9+.#/-]*)*\b")


def evaluate_language_policy(text: str, *, expected_terms: list[str] | None = None) -> dict[str, Any]:
    expected_terms = expected_terms or []
    has_korean = bool(HANGUL_RE.search(text or ""))
    preserved = [term for term in expected_terms if term and term in text]
    missing = [term for term in expected_terms if term and term not in text]
    return {
        "ok": has_korean and not missing,
        "has_korean_explanation": has_korean,
        "expected_english_terms": expected_terms,
        "preserved_terms": preserved,
        "missing_terms": missing,
        "policy": "한국어 중심 설명 + 영어 기술용어/고유명사 보존",
    }


def extract_expected_terms(text: str) -> list[str]:
    found: list[str] = []
    for term in TECH_TERMS:
        if term in text and term not in found:
            found.append(term)
    for match in LATIN_TECH_RE.findall(text or ""):
        cleaned = match.strip()
        if len(cleaned) >= 3 and (cleaned.isupper() or any(ch.isupper() for ch in cleaned[1:])) and cleaned not in found:
            found.append(cleaned)
    return found[:20]


def evaluate_candidate_quality(envelope: dict[str, Any], source_text: str = "", *, gold: dict[str, Any] | None = None) -> dict[str, Any]:
    expected_terms = extract_expected_terms(source_text)
    checks: list[dict[str, Any]] = []
    scores = {"schema_compliance": 1.0, "summary_quality": 0.0, "title_quality": 0.0, "mapping_quality": 0.0, "language_policy": 0.0}

    nodes = envelope.get("node_candidates") or []
    claims = envelope.get("claim_candidates") or []
    mappings = envelope.get("mapping_candidates") or []
    summaries = [node.get("summary", "") for node in nodes if isinstance(node, dict)]
    titles = [node.get("title", "") for node in nodes if isinstance(node, dict)]
    reasons = [mapping.get("reason", "") for mapping in mappings if isinstance(mapping, dict)]
    combined = "\n".join(str(item) for item in [*summaries, *titles, *reasons, *[claim.get("statement", "") for claim in claims if isinstance(claim, dict)]])
    language = evaluate_language_policy(combined, expected_terms=expected_terms[:8]) if combined else {"ok": False, "reason": "no candidate text"}
    checks.append({"kind": "language_policy", **language})
    scores["language_policy"] = 1.0 if language.get("ok") else 0.5 if language.get("has_korean_explanation") else 0.0

    good_summaries = [summary for summary in summaries if isinstance(summary, str) and len(summary.strip()) >= 30 and HANGUL_RE.search(summary)]
    scores["summary_quality"] = min(1.0, len(good_summaries) / max(1, len(nodes))) if nodes else 0.0
    checks.append({"kind": "summary_quality", "ok": bool(good_summaries), "summary_count": len(summaries), "good_summary_count": len(good_summaries)})

    generic_titles = {"개념", "기술", "문서", "요약", "분석", "시스템"}
    good_titles = [title for title in titles if isinstance(title, str) and title.strip() and title.strip() not in generic_titles and len(title.strip()) <= 80]
    scores["title_quality"] = min(1.0, len(good_titles) / max(1, len(nodes))) if nodes else 0.0
    checks.append({"kind": "title_quality", "ok": bool(good_titles), "titles": titles})

    valid_mappings = [m for m in mappings if isinstance(m, dict) and m.get("mapping_action") in {"link_to_existing", "create_separate", "merge_candidate"} and m.get("evidence_claim_keys") and m.get("reason")]
    scores["mapping_quality"] = min(1.0, len(valid_mappings) / max(1, len(mappings))) if mappings else 0.0
    checks.append({"kind": "mapping_quality", "ok": bool(valid_mappings) if mappings else True, "mapping_count": len(mappings), "valid_mapping_count": len(valid_mappings)})

    return {
        "status": "ok",
        "gold_available": bool(gold),
        "scores": scores,
        "checks": checks,
        "overall_score": round(sum(scores.values()) / len(scores), 3),
    }
