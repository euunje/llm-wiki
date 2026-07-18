"""Phase 2 candidate JSON validation for schema-bound LLM outputs."""

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
REF_KINDS = {"existing_node", "new_node"}
MAPPING_ACTIONS = {"link_to_existing", "create_separate", "merge_candidate"}
CLAIM_RELATION_TYPES = {"defines", "describes", "causes", "supports", "contradicts", "part_of", "uses", "related_to"}


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
    _scan_forbidden_keys(payload, "payload", errors)
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
            _validate_common_candidate(field, index, item, errors)
    _validate_candidate_graph(payload, errors)
    return {"ok": not errors, "errors": errors}


def _scan_forbidden_keys(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_KEYS and child_path != key:
                errors.append(f"Forbidden LLM output key present at {child_path}: {key}")
            _scan_forbidden_keys(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, f"{path}[{index}]", errors)


def _validate_common_candidate(field: str, index: int, item: dict[str, Any], errors: list[str]) -> None:
    prefix = f"{field}[{index}]"
    if "review_route" not in item:
        errors.append(f"{prefix} missing review_route")
    if "review_reason" in item and not isinstance(item.get("review_reason"), str):
        errors.append(f"{prefix}.review_reason must be a string")
    if "related_candidate_keys" in item and not _is_str_list(item.get("related_candidate_keys")):
        errors.append(f"{prefix}.related_candidate_keys must be an array of strings")
    if field == "claim_candidates":
        _validate_claim_candidate(prefix, item, errors)
    elif field == "node_candidates":
        _validate_node_candidate(prefix, item, errors)
    elif field == "relation_candidates":
        _validate_relation_candidate(prefix, item, errors)
    elif field == "mapping_candidates":
        _validate_mapping_candidate(prefix, item, errors)
    elif field == "claim_conflict_candidates":
        _validate_conflict_candidate(prefix, item, errors)


def _validate_candidate_graph(payload: dict[str, Any], errors: list[str]) -> None:
    keys_by_field: dict[str, set[str]] = {}
    all_keys: set[str] = set()
    for field in ARRAY_FIELDS:
        keys = {item.get("candidate_key") for item in payload.get(field, []) if isinstance(item, dict)}
        keys_by_field[field] = {key for key in keys if isinstance(key, str)}
        for key in keys_by_field[field]:
            if key in all_keys:
                errors.append(f"Duplicate candidate_key in envelope: {key}")
            all_keys.add(key)
    claim_keys = keys_by_field.get("claim_candidates", set())
    node_keys = keys_by_field.get("node_candidates", set())
    for field in ARRAY_FIELDS:
        for index, item in enumerate(payload.get(field, [])):
            if not isinstance(item, dict):
                continue
            prefix = f"{field}[{index}]"
            for key in item.get("related_candidate_keys", []) or []:
                if key not in all_keys:
                    errors.append(f"{prefix}.related_candidate_keys references unknown candidate_key: {key}")
            for claim_key in item.get("evidence_claim_keys", []) or []:
                if claim_key not in claim_keys:
                    errors.append(f"{prefix}.evidence_claim_keys references unknown claim candidate_key: {claim_key}")
            for ref_field in ("subject_ref", "object_ref", "source_ref", "target_ref", "incoming_ref"):
                ref = item.get(ref_field)
                if isinstance(ref, dict) and ref.get("kind") == "new_node" and ref.get("candidate_key") not in node_keys:
                    errors.append(f"{prefix}.{ref_field} references unknown node candidate_key: {ref.get('candidate_key')}")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_ref(prefix: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{prefix} must be an object")
        return
    kind = value.get("kind")
    if kind not in REF_KINDS:
        errors.append(f"{prefix}.kind must be one of {sorted(REF_KINDS)}")
    if kind == "existing_node" and not _is_non_empty_string(value.get("id")):
        errors.append(f"{prefix}.id is required for existing_node")
    if kind == "new_node" and not _is_non_empty_string(value.get("candidate_key")):
        errors.append(f"{prefix}.candidate_key is required for new_node")
    forbidden = set(value) - {"kind", "id", "candidate_key"}
    if forbidden:
        errors.append(f"{prefix} has unsupported keys: {sorted(forbidden)}")


def _validate_claim_candidate(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    if not _is_non_empty_string(item.get("statement")):
        errors.append(f"{prefix}.statement is required")
    relation_type = item.get("claim_relation_type")
    if not _is_non_empty_string(relation_type):
        errors.append(f"{prefix}.claim_relation_type is required")
    elif relation_type not in CLAIM_RELATION_TYPES:
        errors.append(f"{prefix}.claim_relation_type is not allowed: {relation_type}")
    _validate_ref(f"{prefix}.subject_ref", item.get("subject_ref"), errors)
    _validate_ref(f"{prefix}.object_ref", item.get("object_ref"), errors)
    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{prefix}.evidence must be a non-empty array")
    else:
        for ev_index, evidence_item in enumerate(evidence):
            _validate_evidence(f"{prefix}.evidence[{ev_index}]", evidence_item, errors)
    _validate_confidence(prefix, item, errors)


def _validate_evidence(prefix: str, item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return
    if not _is_non_empty_string(item.get("source_id")):
        errors.append(f"{prefix}.source_id is required")
    if not _is_non_empty_string(item.get("chunk_id")):
        errors.append(f"{prefix}.chunk_id is required")
    locator = item.get("locator")
    if not isinstance(locator, dict):
        errors.append(f"{prefix}.locator must be an object")
        return
    if not isinstance(locator.get("char_start"), int) or not isinstance(locator.get("char_end"), int):
        errors.append(f"{prefix}.locator char_start/char_end must be integers")
    if not _is_non_empty_string(locator.get("quote")):
        errors.append(f"{prefix}.locator.quote is required")


def _validate_node_candidate(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    if item.get("node_type") != "concept":
        errors.append(f"{prefix}.node_type must be concept")
    if not _is_non_empty_string(item.get("title")):
        errors.append(f"{prefix}.title is required")
    if "tags" in item:
        errors.append(f"{prefix}.tags is not part of candidate.v1; use title/aliases/mapping/relation fields")
    if "aliases" not in item or not _is_str_list(item.get("aliases")):
        errors.append(f"{prefix}.aliases must be an array of strings")
    if not _is_non_empty_string(item.get("summary")):
        errors.append(f"{prefix}.summary is required")
    if "evidence_claim_keys" not in item or not _is_str_list(item.get("evidence_claim_keys")) or not item.get("evidence_claim_keys"):
        errors.append(f"{prefix}.evidence_claim_keys must be a non-empty array of strings")


def _validate_relation_candidate(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    _validate_ref(f"{prefix}.source_ref", item.get("source_ref"), errors)
    if not _is_non_empty_string(item.get("relation_type")):
        errors.append(f"{prefix}.relation_type is required")
    _validate_ref(f"{prefix}.target_ref", item.get("target_ref"), errors)
    if "evidence_claim_keys" not in item or not _is_str_list(item.get("evidence_claim_keys")) or not item.get("evidence_claim_keys"):
        errors.append(f"{prefix}.evidence_claim_keys must be a non-empty array of strings")
    _validate_confidence(prefix, item, errors)


def _validate_mapping_candidate(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    _validate_ref(f"{prefix}.incoming_ref", item.get("incoming_ref"), errors)
    action = item.get("mapping_action")
    if action not in MAPPING_ACTIONS:
        errors.append(f"{prefix}.mapping_action must be one of {sorted(MAPPING_ACTIONS)}")
    if action in {"link_to_existing", "merge_candidate"} and not _is_non_empty_string(item.get("existing_node_id")):
        errors.append(f"{prefix}.existing_node_id is required for {action}")
    if action == "create_separate" and item.get("existing_node_id") not in (None, ""):
        errors.append(f"{prefix}.existing_node_id must be empty for create_separate")
    if "evidence_claim_keys" not in item or not _is_str_list(item.get("evidence_claim_keys")) or not item.get("evidence_claim_keys"):
        errors.append(f"{prefix}.evidence_claim_keys must be a non-empty array of strings")
    if not _is_non_empty_string(item.get("reason")):
        errors.append(f"{prefix}.reason is required")
    _validate_confidence(prefix, item, errors)


def _validate_conflict_candidate(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    if not _is_non_empty_string(item.get("claim_ref_a")):
        errors.append(f"{prefix}.claim_ref_a is required")
    if not _is_non_empty_string(item.get("claim_ref_b")):
        errors.append(f"{prefix}.claim_ref_b is required")
    if not _is_non_empty_string(item.get("conflict_scope")):
        errors.append(f"{prefix}.conflict_scope is required")
    if not _is_non_empty_string(item.get("reason")):
        errors.append(f"{prefix}.reason is required")
    _validate_confidence(prefix, item, errors)


def _validate_confidence(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    if "model_confidence" not in item:
        return
    value = item.get("model_confidence")
    if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        errors.append(f"{prefix}.model_confidence must be between 0 and 1")
