"""Phase 2 prompt versioning and default quality prompt policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect


PHASE2_LANGUAGE_POLICY = (
    "한국어 중심 설명으로 작성하되 RAG, LLM, OpenCode, Claude Code, Palantir, "
    "SpaceX 같은 기술 용어/고유명사/제품명/약어/모델명은 원문 영어를 보존한다."
)

DEFAULT_PROMPTS: dict[str, str] = {
    "extract_claims": f"""너는 LLM Wiki Local의 후보 제안자다.
반드시 candidate.v1 JSON만 출력한다. 영구 ID, human_decision, retry_instruction, approved, rejected, replaced, needs_human_review는 출력하지 않는다.
claim_candidates에는 원문 evidence가 있는 주장만 넣고, node_candidates에는 title/aliases/summary/evidence_claim_keys를 넣는다.
{PHASE2_LANGUAGE_POLICY}
title은 개념을 대표해야 하며 너무 일반적인 제목을 피한다. aliases에는 영어 약어와 고유명사를 보존한다.""",
    "map": f"""기존 wiki allow-list와 신규 node 후보를 비교해 mapping_candidates를 candidate.v1 안에 작성한다.
mapping_action은 link_to_existing, create_separate, merge_candidate 중 하나만 사용한다.
existing_node_id는 제공된 allow-list 안의 ID만 사용한다. 임의 tags 필드를 만들지 않는다.
{PHASE2_LANGUAGE_POLICY}
reason/review_reason에는 한국어 중심으로 판단 근거를 설명한다.""",
    "link": f"""claim/node 후보 사이의 relation_candidates를 candidate.v1 안에 작성한다.
같은 응답의 신규 node는 candidate_key로 참조하고 evidence_claim_keys를 반드시 제공한다.
{PHASE2_LANGUAGE_POLICY}""",
    "summarize": f"""Source 또는 Concept를 사람이 검토 가능한 한국어 중심 요약으로 압축한다.
핵심 주장 누락, 원문 왜곡, 근거 없는 단정을 피한다. 기술 용어와 고유명사는 영어를 보존한다.
요약 artifact에는 source_refs/evidence_refs를 포함한다.""",
    "compile": f"""승인 전 자동 Vault 반영 없이 WikiPage preview Markdown을 생성한다.
YAML frontmatter, Claim/Source/Concept 링크, 관련 개념을 포함한다. {PHASE2_LANGUAGE_POLICY}""",
    "ask": f"""검색/RAG context를 기반으로 답한다. 답변은 한국어 중심이며 기술 용어와 고유명사는 영어를 보존한다.
사용한 Source/Claim evidence refs를 artifact에 포함한다.""",
}


def create_prompt_version(
    db_path: Path,
    task_type: str,
    version_label: str,
    prompt_text: str,
    *,
    state: str = "test",
    change_note: str | None = None,
    created_by: str = "system",
) -> str:
    if state not in {"test", "confirmed", "archived"}:
        raise ValueError(f"Invalid prompt state: {state}")
    prompt_id = new_id("prompt")
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO prompt_versions (id, task_type, version_label, state, prompt_text, change_note, created_by, created_at, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (prompt_id, task_type, version_label, state, prompt_text, change_note, created_by, now, now if state == "confirmed" else None),
        )
        conn.commit()
        return prompt_id
    finally:
        conn.close()


def ensure_default_prompts(db_path: Path, *, created_by: str = "system") -> list[str]:
    created: list[str] = []
    conn = connect(db_path)
    try:
        for task_type, prompt_text in DEFAULT_PROMPTS.items():
            row = conn.execute(
                "SELECT id FROM prompt_versions WHERE task_type = ? AND state = 'confirmed' ORDER BY created_at DESC LIMIT 1",
                (task_type,),
            ).fetchone()
            if row:
                continue
            prompt_id = new_id("prompt")
            now = utc_now()
            conn.execute(
                """
                INSERT INTO prompt_versions (id, task_type, version_label, state, prompt_text, change_note, created_by, created_at, confirmed_at)
                VALUES (?, ?, ?, 'confirmed', ?, ?, ?, ?, ?)
                """,
                (prompt_id, task_type, "phase2-default-v1", prompt_text, "Phase 2 default prompt with language and schema policy", created_by, now, now),
            )
            created.append(prompt_id)
        conn.commit()
        return created
    finally:
        conn.close()


def get_active_prompt(db_path: Path, task_type: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT * FROM prompt_versions
            WHERE task_type = ? AND state = 'confirmed'
            ORDER BY confirmed_at DESC, created_at DESC
            LIMIT 1
            """,
            (task_type,),
        ).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    ensure_default_prompts(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM prompt_versions WHERE task_type = ? AND state = 'confirmed' ORDER BY created_at DESC LIMIT 1",
            (task_type,),
        ).fetchone()
        if not row:
            raise ValueError(f"No active prompt for task_type: {task_type}")
        return dict(row)
    finally:
        conn.close()


def confirm_prompt_version(db_path: Path, prompt_id: str) -> None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT task_type FROM prompt_versions WHERE id = ?", (prompt_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown prompt_version_id: {prompt_id}")
        now = utc_now()
        conn.execute("UPDATE prompt_versions SET state = 'archived' WHERE task_type = ? AND state = 'confirmed'", (row[0],))
        conn.execute("UPDATE prompt_versions SET state = 'confirmed', confirmed_at = ? WHERE id = ?", (now, prompt_id))
        conn.commit()
    finally:
        conn.close()


def list_prompt_versions(db_path: Path, task_type: str | None = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if task_type:
            rows = conn.execute("SELECT * FROM prompt_versions WHERE task_type = ? ORDER BY created_at", (task_type,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM prompt_versions ORDER BY task_type, created_at").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
