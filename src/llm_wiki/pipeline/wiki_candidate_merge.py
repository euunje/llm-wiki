from __future__ import annotations

from collections import OrderedDict

from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate
from llm_wiki.slugify import canonical_name


def merge_wiki_page_candidates(candidates: list[WikiPageCandidate]) -> list[WikiPageCandidate]:
    grouped: OrderedDict[str, WikiPageCandidate] = OrderedDict()
    for candidate in candidates:
        key = canonical_name(candidate.title, kind="concept") or candidate.candidate_key
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = candidate
            continue
        existing.aliases = _merge_strs(existing.aliases, [candidate.title, *candidate.aliases])
        existing.keywords = _merge_strs(existing.keywords, candidate.keywords)
        existing.tags = _merge_strs(existing.tags, candidate.tags)
        existing.body_outline = _merge_strs(existing.body_outline, candidate.body_outline)
        existing.summary = _choose_summary(existing.summary, candidate.summary)
        existing.draft_body = _merge_body(existing.draft_body, candidate.draft_body)
        existing.source_section_refs = _merge_refs(existing.source_section_refs, candidate.source_section_refs)
        existing.evidence_claims = _merge_claims(existing.evidence_claims, candidate.evidence_claims)
        existing.merged_from = _merge_strs(existing.merged_from, [candidate.candidate_key, *candidate.merged_from])
    return list(grouped.values())


def _merge_strs(left: list[str], right: list[str]) -> list[str]:
    seen: OrderedDict[str, str] = OrderedDict()
    for item in [*left, *right]:
        text = item.strip()
        if not text:
            continue
        seen.setdefault(text.casefold(), text)
    return list(seen.values())


def _choose_summary(left: str, right: str) -> str:
    return left if len(left.strip()) >= len(right.strip()) else right


def _merge_body(left: str, right: str) -> str:
    if not left.strip():
        return right
    if not right.strip() or right.strip() in left:
        return left
    return f"{left.rstrip()}\n\n{right.strip()}"


def _merge_refs(left: list[SourceSectionRef], right: list[SourceSectionRef]) -> list[SourceSectionRef]:
    seen: OrderedDict[tuple[str, int, int], SourceSectionRef] = OrderedDict()
    for item in [*left, *right]:
        seen[(item.chunk_id, item.char_start, item.char_end)] = item
    return list(seen.values())


def _merge_claims(left: list[EvidenceClaim], right: list[EvidenceClaim]) -> list[EvidenceClaim]:
    seen: OrderedDict[str, EvidenceClaim] = OrderedDict()
    for item in [*left, *right]:
        seen[item.claim_id] = item
    return list(seen.values())
