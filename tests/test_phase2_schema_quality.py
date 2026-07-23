from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from llm_wiki.cli import build_parser
from llm_wiki.db.schema import connect
from llm_wiki.quality import evaluate_candidate_quality, evaluate_language_policy
from llm_wiki.schema import validate_candidate_envelope


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _init_ingest_pipeline(workspace: Path, sample: Path) -> str:
    exit_code, payload = _invoke(["init"], workspace)
    assert exit_code == 0, payload
    exit_code, payload = _invoke(["ingest", str(sample)], workspace)
    assert exit_code == 0, payload
    source_id = str(payload["source_id"])
    assert _invoke(["normalize", source_id], workspace)[0] == 0
    assert _invoke(["chunk", source_id], workspace)[0] == 0
    return source_id


def _valid_envelope(source_id: str) -> dict[str, object]:
    return {
        "task_type": "extract_claims",
        "source_id": source_id,
        "schema_version": "candidate.v1",
        "claim_candidates": [
            {
                "candidate_key": "claim_01",
                "statement": "RAG는 외부 지식 검색을 통해 LLM 응답을 보강한다.",
                "claim_relation_type": "describes",
                "subject_ref": {"kind": "new_node", "candidate_key": "node_01"},
                "object_ref": {"kind": "existing_node", "id": "concept_rag"},
                "evidence": [
                    {
                        "source_id": source_id,
                        "chunk_id": "chunk_01",
                        "locator": {"char_start": 0, "char_end": 30, "quote": "RAG는 외부 지식 검색"},
                    }
                ],
                "model_confidence": 0.8,
                "review_route": "normal_review",
                "review_reason": "원문 근거가 있습니다.",
                "related_candidate_keys": ["node_01"],
            }
        ],
        "node_candidates": [
            {
                "candidate_key": "node_01",
                "node_type": "concept",
                "title": "RAG",
                "aliases": ["Retrieval-Augmented Generation", "LLM"],
                "summary": "RAG는 외부 지식 검색을 사용해 LLM 응답의 근거성을 보강하는 패턴이다.",
                "evidence_claim_keys": ["claim_01"],
                "review_route": "normal_review",
                "review_reason": "핵심 개념 후보입니다.",
                "related_candidate_keys": ["claim_01"],
            }
        ],
        "relation_candidates": [],
        "mapping_candidates": [
            {
                "candidate_key": "mapping_01",
                "incoming_ref": {"kind": "new_node", "candidate_key": "node_01"},
                "existing_node_id": "concept_rag",
                "mapping_action": "merge_candidate",
                "evidence_claim_keys": ["claim_01"],
                "reason": "기존 RAG 개념과 의미 범위가 겹칩니다.",
                "model_confidence": 0.75,
                "review_route": "needs_merge_decision",
                "review_reason": "병합 판단이 필요합니다.",
                "related_candidate_keys": ["node_01"],
            }
        ],
        "claim_conflict_candidates": [],
    }


def test_phase2_candidate_schema_accepts_title_mapping_contract() -> None:
    validation = validate_candidate_envelope(_valid_envelope("source_abc"))
    assert validation["ok"] is True
    assert validation["errors"] == []


def test_phase2_candidate_schema_rejects_tags_and_bad_mapping() -> None:
    envelope = _valid_envelope("source_abc")
    envelope["node_candidates"][0]["tags"] = ["bad"]  # type: ignore[index]
    envelope["mapping_candidates"][0]["mapping_action"] = "tag_as"  # type: ignore[index]
    validation = validate_candidate_envelope(envelope)
    assert validation["ok"] is False
    assert any("tags" in error for error in validation["errors"])
    assert any("mapping_action" in error for error in validation["errors"])


def test_language_policy_requires_korean_explanation_and_preserves_english_terms() -> None:
    result = evaluate_language_policy(
        "이 문서는 Claude Code와 OpenCode의 token overhead를 비교한다.",
        expected_terms=["Claude Code", "OpenCode", "token"],
    )
    assert result["ok"] is True
    bad = evaluate_language_policy("This document compares token overhead.", expected_terms=["token"])
    assert bad["ok"] is False


def test_extract_claims_persists_candidates_and_quality_report(workspace: Path, samples_dir: Path) -> None:
    source_id = _init_ingest_pipeline(workspace, samples_dir / "rag.md")
    exit_code, payload = _invoke(["extract-claims", source_id], workspace)
    assert exit_code == 0, payload
    assert payload["status"] == "ok"
    assert payload["candidate_count"] >= 2
    assert payload["validation"]["ok"] is True
    assert payload["quality_evaluation"]["scores"]["summary_quality"] > 0
    assert payload["quality_evaluation"]["scores"]["title_quality"] > 0
    assert payload["persisted_candidates"]

    conn = connect(workspace / "data" / "wiki.sqlite")
    try:
        count = conn.execute("SELECT COUNT(*) FROM review_candidates WHERE source_id = ?", (source_id,)).fetchone()[0]
        prompts = conn.execute("SELECT COUNT(*) FROM prompt_versions WHERE state = 'confirmed'").fetchone()[0]
    finally:
        conn.close()
    assert count >= 2
    assert prompts >= 2


def test_map_candidate_generation_flow(workspace: Path, samples_dir: Path) -> None:
    source_id = _init_ingest_pipeline(workspace, samples_dir / "rag.md")
    from llm_wiki.cli.phase1_placeholders import run_map

    exit_code, payload = run_map(SimpleNamespace(path=str(workspace), source_id=source_id))
    assert exit_code == 0, payload
    assert payload["validation"]["ok"] is True
    assert payload["mapping_candidates"]
    assert payload["persisted_candidates"]


def test_quality_evaluator_reports_gold_availability() -> None:
    result = evaluate_candidate_quality(_valid_envelope("source_abc"), "RAG와 LLM 설명")
    assert result["gold_available"] is False
    assert result["scores"]["mapping_quality"] > 0
