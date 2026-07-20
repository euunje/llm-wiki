from __future__ import annotations

import argparse
import json
import re

from llm_wiki.common import ensure_parent, relative_to
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.llm.chat import call_json_task
from llm_wiki.quality import evaluate_candidate_quality, extract_expected_terms
from llm_wiki.schema import build_empty_candidate_envelope, get_active_prompt, insert_candidates_from_envelope, validate_candidate_envelope
from llm_wiki.workspace import resolve_workspace


PHASE2_NOTE = "Phase 2 quality behavior: schema-bound Korean explanation with English technical/proper terms preserved."


def _ensure_source_exists(db_path, source_id: str) -> None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT id FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown source_id: {source_id}")
    finally:
        conn.close()


def _artifact_target(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value) or "target"


def _source_row(workspace, source_id: str) -> dict[str, object]:
    conn = connect(workspace.db)
    try:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown source_id: {source_id}")
        return dict(row)
    finally:
        conn.close()


def _source_text_and_chunks(workspace, source_id: str) -> tuple[str, list[dict[str, object]]]:
    source = _source_row(workspace, source_id)
    conn = connect(workspace.db)
    try:
        rows = conn.execute("SELECT * FROM source_chunks WHERE source_id = ? ORDER BY chunk_index", (source_id,)).fetchall()
        chunks = [dict(row) for row in rows]
    finally:
        conn.close()
    if chunks:
        return "\n\n".join(str(chunk["text"]) for chunk in chunks), chunks
    path_value = source.get("normalized_path") or source.get("raw_path")
    if not path_value:
        return "", []
    text = (workspace.root / str(path_value)).read_text(encoding="utf-8")
    fallback_chunk = {
        "id": "chunk_inline_0",
        "source_id": source_id,
        "chunk_index": 0,
        "text": text[:1200],
        "locator_json": json.dumps({"char_start": 0, "char_end": min(len(text), 1200), "quote": text[:180]}, ensure_ascii=False),
    }
    return text, [fallback_chunk]


def _has_persisted_chunks(workspace, source_id: str) -> bool:
    conn = connect(workspace.db)
    try:
        return bool(conn.execute("SELECT 1 FROM source_chunks WHERE source_id = ? LIMIT 1", (source_id,)).fetchone())
    finally:
        conn.close()


def _clean_title(raw: str) -> str:
    title = re.sub(r"[_-]+", " ", raw).strip()
    title = re.sub(r"\s+", " ", title)
    return title[:80] or "Source Concept"


def _first_sentence(text: str, limit: int = 220) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return "원문에서 핵심 내용을 추출할 수 없습니다."
    for sep in (". ", "。", "\n"):
        if sep in clean[:limit]:
            return clean[: clean.find(sep) + len(sep)].strip()
    return clean[:limit].strip()


def _korean_summary(title: str, text: str) -> str:
    terms = extract_expected_terms(text)
    preserved = ", ".join(terms[:5])
    first = _first_sentence(text)
    suffix = f" 주요 용어는 {preserved}를 보존한다." if preserved else ""
    return f"이 자료는 {title}와 관련된 핵심 주장과 개념을 정리한다. 원문 근거를 기준으로 '{first}' 내용을 중심으로 검토한다.{suffix}"


def _build_candidate_envelope(workspace, source_id: str, *, include_mapping: bool = False, include_relation: bool = False) -> dict[str, object]:
    source = _source_row(workspace, source_id)
    text, chunks = _source_text_and_chunks(workspace, source_id)
    chunk = chunks[0] if chunks else {"id": "chunk_inline_0", "text": text, "locator_json": "{}"}
    chunk_text = str(chunk.get("text") or text)
    locator = json.loads(str(chunk.get("locator_json") or "{}")) if isinstance(chunk.get("locator_json"), str) else {}
    quote = _first_sentence(chunk_text, 180)
    title = _clean_title(str(source.get("title") or source_id))
    terms = extract_expected_terms(text)
    aliases = [term for term in terms if term.lower() not in title.lower()][:8]
    claim = {
        "candidate_key": "claim_01",
        "statement": f"{title}의 핵심 내용은 원문 근거에 기반해 wiki 후보로 검토할 수 있다.",
        "claim_relation_type": "describes",
        "subject_ref": {"kind": "new_node", "candidate_key": "node_01"},
        "object_ref": {"kind": "existing_node", "id": "source_context"},
        "qualifiers": {},
        "evidence": [
            {
                "source_id": source_id,
                "chunk_id": str(chunk.get("id") or "chunk_inline_0"),
                "locator": {
                    "char_start": int(locator.get("start_offset", locator.get("char_start", 0)) or 0),
                    "char_end": int(locator.get("end_offset", locator.get("char_end", max(1, len(quote)))) or max(1, len(quote))),
                    "quote": quote,
                },
            }
        ],
        "model_confidence": 0.62,
        "review_route": "normal_review",
        "review_reason": "원문 근거가 있는 1차 claim 후보입니다.",
        "related_candidate_keys": ["node_01"],
    }
    node = {
        "candidate_key": "node_01",
        "node_type": "concept",
        "title": title,
        "aliases": aliases,
        "summary": _korean_summary(title, text),
        "evidence_claim_keys": ["claim_01"],
        "review_route": "normal_review",
        "review_reason": "새 wiki 개념 후보로 검토할 수 있습니다.",
        "related_candidate_keys": ["claim_01"],
    }
    envelope: dict[str, object] = {
        "task_type": "extract_claims",
        "source_id": source_id,
        "schema_version": "candidate.v1",
        "claim_candidates": [claim],
        "node_candidates": [node],
        "relation_candidates": [],
        "mapping_candidates": [],
        "claim_conflict_candidates": [],
    }
    if include_mapping:
        envelope["task_type"] = "map"
        envelope["mapping_candidates"] = [
            {
                "candidate_key": "mapping_01",
                "incoming_ref": {"kind": "new_node", "candidate_key": "node_01"},
                "existing_node_id": "",
                "mapping_action": "create_separate",
                "evidence_claim_keys": ["claim_01"],
                "reason": "현재 CLI allow-list 안에서 동일한 기존 wiki 개념을 확정할 근거가 부족하므로 신규 개념으로 분리 검토합니다.",
                "model_confidence": 0.55,
                "review_route": "normal_review",
                "review_reason": "기존 wiki 매핑 후보가 부족해 신규 생성 후보로 라우팅합니다.",
                "related_candidate_keys": ["node_01"],
            }
        ]
    if include_relation:
        envelope["task_type"] = "link"
        envelope["relation_candidates"] = [
            {
                "candidate_key": "relation_01",
                "source_ref": {"kind": "new_node", "candidate_key": "node_01"},
                "relation_type": "related_to",
                "target_ref": {"kind": "existing_node", "id": "source_context"},
                "evidence_claim_keys": ["claim_01"],
                "model_confidence": 0.5,
                "review_route": "normal_review",
                "review_reason": "Source context와의 기본 관계 후보입니다.",
                "related_candidate_keys": ["node_01", "claim_01"],
            }
        ]
    return envelope


def run_extract_claims(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    _ensure_source_exists(workspace.db, args.source_id)
    prompt = get_active_prompt(workspace.db, "extract_claims")
    job_id = create_job(workspace.db, "extract_claims", target_type="source", target_id=args.source_id)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="phase2_quality_runner",
        task_type="extract_claims",
        prompt_version_id=prompt["id"],
        input_refs=[{"kind": "source", "source_id": args.source_id}],
    )
    source_text, _ = _source_text_and_chunks(workspace, args.source_id)
    llm_attempt: dict[str, object] | None = None
    if getattr(args, "use_llm", False):
        model_id = "chat_default"
        user_prompt = (
            "다음 Source를 candidate.v1 JSON으로만 변환하세요. 설명 문장, markdown fence, 주석은 금지입니다. "
            "영구 ID와 사람 결정 필드는 금지입니다. candidate_key는 반드시 claim_01, node_01 같은 형식입니다. "
            f"source_id={args.source_id}\n\n"
            "반드시 아래 field 이름을 그대로 사용하세요. claim에는 statement, claim_relation_type, subject_ref, object_ref, evidence, review_route가 필요합니다.\n"
            "파싱 안정성을 위해 claim_candidates는 정확히 1개, node_candidates는 정확히 1개만 작성하고 relation/mapping/conflict 배열은 비워두세요.\n"
            "claim evidence에는 source_id, chunk_id, locator.char_start, locator.char_end, locator.quote를 포함하세요.\n"
            "node title/summary/reason은 한국어 중심 설명을 쓰되 영어 기술용어와 고유명사는 보존하세요.\n"
            "허용 review_route: normal_review, needs_merge_decision, needs_retry, conflict_flag.\n"
            "허용 claim_relation_type: defines, describes, causes, supports, contradicts, part_of, uses, related_to.\n"
            "필수 JSON skeleton:\n"
            "{\n"
            "  \"task_type\": \"extract_claims\",\n"
            f"  \"source_id\": \"{args.source_id}\",\n"
            "  \"schema_version\": \"candidate.v1\",\n"
            "  \"claim_candidates\": [{\"candidate_key\": \"claim_01\", \"statement\": \"...\", \"claim_relation_type\": \"describes\", \"subject_ref\": {\"kind\": \"new_node\", \"candidate_key\": \"node_01\"}, \"object_ref\": {\"kind\": \"existing_node\", \"id\": \"source_context\"}, \"evidence\": [{\"source_id\": \"...\", \"chunk_id\": \"...\", \"locator\": {\"char_start\": 0, \"char_end\": 10, \"quote\": \"...\"}}], \"review_route\": \"normal_review\", \"review_reason\": \"...\", \"related_candidate_keys\": [\"node_01\"]}],\n"
            "  \"node_candidates\": [{\"candidate_key\": \"node_01\", \"node_type\": \"concept\", \"title\": \"...\", \"aliases\": [], \"summary\": \"...\", \"evidence_claim_keys\": [\"claim_01\"], \"review_route\": \"normal_review\", \"review_reason\": \"...\", \"related_candidate_keys\": [\"claim_01\"]}],\n"
            "  \"relation_candidates\": [],\n"
            "  \"mapping_candidates\": [],\n"
            "  \"claim_conflict_candidates\": []\n"
            "}\n\n"
            f"SOURCE TEXT:\n{source_text[:2500]}"
        )
        try:
            llm_result = call_json_task(
                workspace,
                model_id=model_id,
                system_prompt=str(prompt["prompt_text"]),
                user_prompt=user_prompt,
            )
            parsed = llm_result["parsed_json"]
            if isinstance(parsed, dict):
                parsed.setdefault("task_type", "extract_claims")
                parsed.setdefault("source_id", args.source_id)
                parsed.setdefault("schema_version", "candidate.v1")
                for field in ("claim_candidates", "node_candidates", "relation_candidates", "mapping_candidates", "claim_conflict_candidates"):
                    parsed.setdefault(field, [])
                envelope = parsed
                llm_attempt = {
                    "attempted": True,
                    "status": "parsed",
                    "api_key_present": llm_result.get("api_key_present"),
                    "http_response_size_bytes": llm_result.get("http_response_size_bytes"),
                    "content_preview": str(llm_result.get("content") or "")[:600],
                }
            else:
                envelope = build_empty_candidate_envelope("extract_claims", args.source_id)
                llm_attempt = {"attempted": True, "status": "parse_failed", "reason": "parsed JSON was not an object"}
        except Exception as exc:
            envelope = build_empty_candidate_envelope("extract_claims", args.source_id)
            llm_attempt = {"attempted": True, "status": "failed", "reason": str(exc), "type": exc.__class__.__name__}
    else:
        envelope = _build_candidate_envelope(workspace, args.source_id) if _has_persisted_chunks(workspace, args.source_id) else build_empty_candidate_envelope("extract_claims", args.source_id)
    validation = validate_candidate_envelope(envelope)
    llm_failed = bool(llm_attempt and llm_attempt.get("attempted") and llm_attempt.get("status") in {"failed", "parse_failed"})
    persisted = insert_candidates_from_envelope(workspace.db, envelope, run_id) if validation["ok"] else []
    quality = evaluate_candidate_quality(envelope, source_text)
    payload = {
        "status": "failed" if llm_failed else ("ok" if validation["ok"] else "failed"),
        "source_id": args.source_id,
        "job_id": job_id,
        "run_id": run_id,
        "prompt_version_id": prompt["id"],
        "prompt_text_used": prompt.get("prompt_text"),
        "candidate_count": sum(len(envelope[field]) for field in ("claim_candidates", "node_candidates", "relation_candidates", "mapping_candidates", "claim_conflict_candidates")),
        "validation": validation,
        "quality_evaluation": quality,
        "llm_attempt": llm_attempt or {"attempted": False},
        "persisted_candidates": persisted,
        "candidate_envelope": envelope,
        "phase_note": PHASE2_NOTE,
    }
    artifact = record_artifact(workspace, "candidate_contract", "extract_claims", payload, "source", args.source_id, run_id)
    succeeded = validation["ok"] and not llm_failed
    update_agent_run(workspace.db, run_id, status="succeeded" if succeeded else "failed", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    update_job(workspace.db, job_id, status="succeeded" if succeeded else "failed", output_refs=[artifact])
    return (0 if succeeded else 1), {**payload, **artifact, "workspace": str(workspace.root), "message": f"Created extract-claims placeholder for {args.source_id}"}


def _placeholder_report(workspace, task_type: str, target: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    job_id = create_job(workspace.db, task_type, target_type="target", target_id=target)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="phase1_placeholder",
        task_type=task_type,
        prompt_version_id=payload.get("prompt_version_id") if isinstance(payload.get("prompt_version_id"), str) else None,
        input_refs=[{"kind": "target", "target": target}],
    )
    body = {"status": "ok", "job_id": job_id, "run_id": run_id, "phase_note": PHASE2_NOTE, **payload}
    artifact = record_artifact(workspace, f"{task_type}_placeholder", task_type, body, "target", _artifact_target(target), run_id)
    ok = body.get("status") not in {"failed", "blocked"} and not (isinstance(body.get("validation"), dict) and not body["validation"].get("ok", True))
    update_agent_run(workspace.db, run_id, status="succeeded" if ok else "failed", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    update_job(workspace.db, job_id, status="succeeded" if ok else "failed", output_refs=[artifact])
    return (0 if ok else 1), {**body, **artifact, "workspace": str(workspace.root), "message": f"Created {task_type} Phase 1 placeholder"}


def run_summarize(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    target = args.target
    source_id = target.split(":", 1)[1] if target.startswith("source:") else target
    _ensure_source_exists(workspace.db, source_id)
    source = _source_row(workspace, source_id)
    text, chunks = _source_text_and_chunks(workspace, source_id)
    title = _clean_title(str(source.get("title") or source_id))
    summary = _korean_summary(title, text)
    prompt = get_active_prompt(workspace.db, "summarize")
    return _placeholder_report(
        workspace,
        "summarize",
        target,
        {"target": target, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "summary": summary, "summary_placeholder": summary, "source_refs": [{"source_id": source_id}], "evidence_refs": [{"source_id": source_id, "chunk_id": chunk.get("id")} for chunk in chunks[:3]], "language_policy": "한국어 중심 설명 + 영어 기술용어/고유명사 보존"},
    )


def run_link(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    source_id = args.target.split(":", 1)[1] if args.target.startswith("source:") else args.target
    prompt = get_active_prompt(workspace.db, "link")
    if source_id.startswith("source_") and _has_persisted_chunks(workspace, source_id):
        envelope = _build_candidate_envelope(workspace, source_id, include_relation=True)
        validation = validate_candidate_envelope(envelope)
        if validation["ok"]:
            insert_candidates_from_envelope(workspace.db, envelope)
        return _placeholder_report(
            workspace,
            "link",
            args.target,
            {"target": args.target, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "relation_candidates": envelope["relation_candidates"], "review_routes": ["normal_review"], "validation": validation, "candidate_envelope": envelope},
        )
    return _placeholder_report(
        workspace,
        "link",
        args.target,
        {"target": args.target, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "relation_candidates": [], "review_routes": []},
    )


def run_map(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    _ensure_source_exists(workspace.db, args.source_id)
    prompt = get_active_prompt(workspace.db, "map")
    if not _has_persisted_chunks(workspace, args.source_id):
        return _placeholder_report(
            workspace,
            "map",
            args.source_id,
            {"source_id": args.source_id, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "mapping_candidates": [], "high_similarity_candidates": [], "phase_note": "Chunk source before Phase 2 mapping quality generation."},
        )
    source_text, _ = _source_text_and_chunks(workspace, args.source_id)
    envelope = _build_candidate_envelope(workspace, args.source_id, include_mapping=True)
    validation = validate_candidate_envelope(envelope)
    persisted = insert_candidates_from_envelope(workspace.db, envelope) if validation["ok"] else []
    quality = evaluate_candidate_quality(envelope, source_text)
    return _placeholder_report(
        workspace,
        "map",
        args.source_id,
        {"source_id": args.source_id, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "mapping_candidates": envelope["mapping_candidates"], "high_similarity_candidates": [], "candidate_envelope": envelope, "validation": validation, "quality_evaluation": quality, "persisted_candidates": persisted},
    )


def run_ask(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    from llm_wiki.search import ask_workspace

    prompt = get_active_prompt(workspace.db, "ask")
    ask_payload = ask_workspace(workspace, args.query)
    return _placeholder_report(
        workspace,
        "ask",
        args.query,
        {"query": args.query, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "candidates": ask_payload["evidence_refs"], "evidence_refs": ask_payload["evidence_refs"], "search_metadata": ask_payload["search_metadata"], "answer": ask_payload["answer"], "answer_placeholder": ask_payload["answer_placeholder"]},
    )


def run_compile(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    prompt = get_active_prompt(workspace.db, "compile")
    exit_code, payload = _placeholder_report(
        workspace,
        "compile",
        args.target,
        {"target": args.target, "prompt_version_id": prompt["id"], "prompt_text_used": prompt.get("prompt_text"), "preview_status": "draft_preview", "phase_note": PHASE2_NOTE},
    )
    preview_dir = workspace.artifacts / "compile" / _artifact_target(args.target)
    preview_path = preview_dir / f"{payload['run_id']}.md"
    ensure_parent(preview_path)
    preview_path.write_text(
        "---\n"
        f'title: "{args.target}"\n'
        "aliases: []\n"
        "status: draft_preview\n"
        "source_refs: []\n"
        "claim_refs: []\n"
        "relation_refs: []\n"
        "---\n\n"
        f"# {args.target}\n\n"
        "## Summary\n\n"
        "이 WikiPage preview는 승인 전 검토용 초안입니다. 한국어 중심 설명을 사용하되 기술 용어와 고유명사는 원문 표기를 보존합니다.\n\n"
        "## Claims\n\n- 후보 Claim은 `review_candidates`와 artifact에서 검토합니다.\n\n"
        "## Sources\n\n- 자동 Vault 반영은 수행하지 않습니다.\n",
        encoding="utf-8",
    )
    payload["preview_path"] = relative_to(workspace.root, preview_path)
    return exit_code, payload
