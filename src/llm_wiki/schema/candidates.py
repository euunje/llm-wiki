from __future__ import annotations

import re
from typing import Any

FORBIDDEN_KEYS = {"human_decision", "retry_instruction", "approved", "rejected", "replaced"}
REVIEW_ROUTES = {"normal_review", "needs_merge_decision", "needs_retry", "conflict_flag"}
KEY_PATTERNS = {
    "claim_candidates": re.compile(r"^claim_\d+$"),
    "node_candidates": re.compile(r"^node_\d+$"),
    "relation_candidates": re.compile(r"^relation_\d+$"),
    "mapping_candidates": re.compile(r"^mapping_\d+$"),
    "claim_conflict_candidates": re.compile(r"^conflict_\d+$"),
}
ARRAY_FIELDS = tuple(KEY_PATTERNS.keys())


def build_empty_candidate_envelope(task_type: str, source_id: str) -> dict[str, Any]:
    return {
        "task_type": task_type,
        "source_id": source_id,
        "schema_version": "candidate.v1",
        "claim_candidates": [],
        "node_candidates": [],
        "relation_candidates": [],
        "mapping_candidates": [],
        "claim_conflict_candidates": [],
    }


def validate_candidate_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore

        schema = {
            "type": "object",
            "required": ["task_type", "source_id", "schema_version", *ARRAY_FIELDS],
            "properties": {
                "task_type": {"type": "string"},
                "source_id": {"type": "string", "pattern": r"^source_"},
                "schema_version": {"type": "string", "const": "candidate.v1"},
                **{field: {"type": "array"} for field in ARRAY_FIELDS},
            },
        }
        jsonschema.validate(payload, schema)
    except ImportError:
        pass
    except Exception as exc:
        errors.append(str(exc))
    for key in ("task_type", "source_id", "schema_version", *ARRAY_FIELDS):
        if key not in payload:
            errors.append(f"Missing required field: {key}")
    for forbidden in FORBIDDEN_KEYS:
        if forbidden in payload:
            errors.append(f"Forbidden LLM output key present: {forbidden}")
    if payload.get("schema_version") != "candidate.v1":
        errors.append("schema_version must be candidate.v1")
    if not str(payload.get("source_id", "")).startswith("source_"):
        errors.append("source_id must start with source_")
    for field in ARRAY_FIELDS:
        items = payload.get(field)
        if not isinstance(items, list):
            errors.append(f"{field} must be an array")
            continue
        pattern = KEY_PATTERNS[field]
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{field}[{index}] must be an object")
                continue
            for forbidden in FORBIDDEN_KEYS:
                if forbidden in item:
                    errors.append(f"{field}[{index}] contains forbidden key: {forbidden}")
            candidate_key = item.get("candidate_key")
            if not isinstance(candidate_key, str) or not pattern.match(candidate_key):
                errors.append(f"{field}[{index}] has invalid candidate_key")
            review_route = item.get("review_route")
            if review_route is not None and review_route not in REVIEW_ROUTES:
                errors.append(f"{field}[{index}] has invalid review_route")
            if "id" in item:
                errors.append(f"{field}[{index}] must not contain permanent id")
    return {"ok": not errors, "errors": errors}
