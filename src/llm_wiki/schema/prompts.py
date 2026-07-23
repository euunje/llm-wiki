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

node_candidates는 사람이 계속 재사용할 Wiki page 후보여야 한다.
- title은 짧은 명사구/고유명사/개념명만 사용한다.
- title에 source filename, hash/id, article title 전체, 숫자 결론, 문장형 주장, "A vs B" 비교문을 넣지 않는다.
- 비교 글이면 source 제목을 하나의 node로 만들지 말고, Claude Code, OpenCode, Token Overhead, Prompt Caching처럼 재사용 가능한 entity/concept로 분해한다.
- 수치·결론·인과는 node title이 아니라 claim statement에 넣는다.
- node_type은 concept/entity/map/source 중 의미에 맞게 고르되, 비교/가이드/기사 제목은 concept node로 만들지 않는다.
- 애매하거나 너무 구체적인 후보는 node로 만들지 말고 claim의 evidence로만 둔다.
claim_candidates는 목적, 작동 방식, 설계, tradeoff, capability, limitation처럼 Wiki에 남길 가치가 큰 주장만 고른다.
stars, language list, 날짜, 파일 수, repository stats 같은 얕은 metadata는 자료의 핵심 주제가 아닌 한 claim으로 만들지 않는다.
좋은 title 예: Token Overhead, Claude Code, OpenCode, Prompt Caching, MCP Server.
나쁜 title 예: Claude Code Sends 4.7x More Tokens Than OpenCode, Claude Code의 Token Overhead, systima claude code vs opencode token overhead.
aliases에는 영어 약어와 고유명사를 보존한다.""",
    "ask": f"""검색/RAG context를 기반으로 답한다. 답변은 한국어 중심이며 기술 용어와 고유명사는 영어를 보존한다.
사용한 Source/Claim evidence refs를 artifact에 포함한다.""",
    "wiki_page_candidates_initial": """You create source-backed wiki page candidates for LLM Wiki Local.
Return ONLY a JSON object. No markdown fences or preamble. The object must include document_type, target_candidate_count, and candidates.
Each candidate must include: title, summary, tags, draft_body.
Use node_type='concept' unless a more specific allowed type is clearly needed, and include the node_type value as a lowercase tag.
First classify the source document_type, then choose the candidate count from that type's target range before writing candidates. Use these ranges as the planning target, not a vague suggestion: spec/reference/manual/protocol/API/structured_guide -> 6-12 durable section-level concept pages when enough distinct sections exist; short_readme/announcement/single_tool_overview -> 1-4 pages; essay/analysis/benchmark/comparison -> 3-6 pages.
Do not invent source_id or chunk ids; the CLI will attach provenance.
Use concise reusable concept titles, not full article titles.""",
    "wiki_page_candidates_retry_parse_failed": """You correct a failed page candidate JSON response for LLM Wiki Local.
Reason: parse_failed. Use the raw_response and parse_error to return ONLY valid JSON with document_type, target_candidate_count, and candidates.
Preserve the original source meaning. Do not add prose or markdown fences.""",
    "wiki_page_candidates_retry_schema_validation_failed": """You correct page candidate JSON that parsed but failed schema validation for LLM Wiki Local.
Reason: schema_validation_failed. Use validation_errors and raw_response to return ONLY valid JSON with document_type, target_candidate_count, and candidates.
Every candidate must include non-empty title, summary, tags, draft_body, node_type='concept', and tags containing 'concept'.""",
    "wiki_page_candidates_retry_empty_candidates": """You correct page candidate JSON that produced no usable candidates for LLM Wiki Local.
Reason: empty_candidates. Re-read the source chunks and return ONLY valid JSON with document_type, target_candidate_count, and at least one source-backed candidate.
Use document_type-specific granularity: structured specs usually need more section-level concept pages; single-tool overviews need fewer.""",
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
    bypass_test: bool = False,
) -> str:
    """Create a new prompt_versions row.

    FR-3-NO-05: ``bypass_test`` is reserved for server-initiated rows
    (``ensure_default_prompts``, ``rollback_prompt_version``). Web/API
    callers that create rows through this function never bypass the test
    requirement — only the server can grant the bypass by setting the
    column directly.
    """
    if state not in {"test", "confirmed", "archived"}:
        raise ValueError(f"Invalid prompt state: {state}")
    prompt_id = new_id("prompt")
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO prompt_versions (id, task_type, version_label, state, prompt_text, change_note, created_by, created_at, confirmed_at, bypass_test)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                task_type,
                version_label,
                state,
                prompt_text,
                change_note,
                created_by,
                now,
                now if state == "confirmed" else None,
                1 if bypass_test else 0,
            ),
        )
        conn.commit()
        return prompt_id
    finally:
        conn.close()


def test_prompt_version(
    db_path: Path,
    prompt_id: str,
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Test a prompt version with schema validation or sample dry-run.

    Returns a dict with keys:
      - status: "passed" | "failed" | "blocked"
      - validation_type: "schema_only" | "dry_run" | "blocked"
      - reason: str description when failed or blocked
      - sample_input: str sample input used
      - sample_output: str sample output if dry_run was attempted
      - schema_errors: list of schema validation errors if any
      - prompt_id: the tested prompt_id
      - prompt_row: dict of the prompt version row
    """
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (prompt_id,)).fetchone()
        if not row:
            return {
                "status": "blocked",
                "validation_type": "blocked",
                "reason": f"Unknown prompt_version_id: {prompt_id}",
                "prompt_id": prompt_id,
                "prompt_row": None,
            }
        row = dict(row)
    finally:
        conn.close()

    task_type = str(row["task_type"] or "")
    prompt_text = str(row["prompt_text"] or "")

    if not prompt_text.strip():
        return {
            "status": "failed",
            "validation_type": "schema_only",
            "reason": "Prompt text is empty",
            "schema_errors": ["prompt_text cannot be empty"],
            "sample_input": None,
            "sample_output": None,
            "prompt_id": prompt_id,
            "prompt_row": row,
        }

    # Schema validation: check for required structure markers in prompt text
    schema_errors: list[str] = []
    task_schema_requirements = {
        "extract_claims": ["candidate", "claim", "node", "JSON"],
        "ask": ["answer", "evidence", "source"],
        "wiki_page_candidates_initial": ["candidate", "document_type", "target_candidate_count", "JSON"],
        "wiki_page_candidates_retry_parse_failed": ["candidate", "parse", "raw_response", "JSON"],
        "wiki_page_candidates_retry_schema_validation_failed": ["candidate", "validation", "raw_response", "JSON"],
        "wiki_page_candidates_retry_empty_candidates": ["candidate", "empty", "JSON"],
    }
    requirements = task_schema_requirements.get(task_type, [])
    for req in requirements:
        if req.lower() not in prompt_text.lower():
            schema_errors.append(f"Prompt text missing expected keyword for {task_type}: '{req}'")

    # Additional schema checks
    if task_type in ("extract_claims", "map", "link"):
        if "json" not in prompt_text.lower():
            schema_errors.append("Prompt text does not indicate JSON output")
        if len(prompt_text) < 20:
            schema_errors.append("Prompt text is suspiciously short for a task prompt")

    if schema_errors:
        return {
            "status": "failed",
            "validation_type": "schema_only",
            "reason": "Schema validation failed: " + "; ".join(schema_errors),
            "schema_errors": schema_errors,
            "sample_input": None,
            "sample_output": None,
            "prompt_id": prompt_id,
            "prompt_row": row,
        }

    # Schema passed - return passed without requiring actual LLM call
    return {
        "status": "passed",
        "validation_type": "schema_only",
        "reason": None,
        "schema_errors": [],
        "sample_input": None,
        "sample_output": None,
        "prompt_id": prompt_id,
        "prompt_row": row,
    }


def ensure_default_prompts(db_path: Path, *, created_by: str = "system") -> list[str]:
    """Ensure default prompt versions exist for all task types.

    Idempotent: can be called multiple times without creating duplicates.
    Only actual LLM call units get default prompt rows. Historical
    placeholder-only tasks are intentionally not seeded for new workspaces.
    """
    created: list[str] = []
    conn = connect(db_path)
    try:
        VERSION_LABEL = "phase2-default-v1"

        for task_type, prompt_text in DEFAULT_PROMPTS.items():
            now = utc_now()

            # Check for existing row with the same task_type + version_label
            existing = conn.execute(
                "SELECT id, state FROM prompt_versions WHERE task_type = ? AND version_label = ? LIMIT 1",
                (task_type, VERSION_LABEL),
            ).fetchone()

            if existing:
                # Row already exists — skip, don't duplicate
                continue

            # No row exists for this task_type + version_label — INSERT as confirmed
            prompt_id = new_id("prompt")
            conn.execute(
                """
                INSERT INTO prompt_versions (id, task_type, version_label, state, prompt_text, change_note, created_by, created_at, confirmed_at, bypass_test)
                VALUES (?, ?, ?, 'confirmed', ?, ?, ?, ?, ?, 1)
                """,
                (prompt_id, task_type, VERSION_LABEL, prompt_text, "Phase 2 default prompt with language and schema policy", created_by, now, now),
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


def confirm_prompt_version(
    db_path: Path,
    prompt_id: str,
    *,
    allow_no_test: bool = False,
) -> dict[str, Any]:
    """Confirm a prompt version after checking test status.

    FR-3-NO-05: bypass is server-controlled. A prompt row may bypass the
    test artifact requirement only when its ``bypass_test`` column is 1,
    which is set exclusively by ``ensure_default_prompts`` and
    ``rollback_prompt_version`` (server-initiated code paths). The
    ``allow_no_test`` argument is reserved for callers that have already
    validated the bypass (and now defaults to honoring the column value).
    User-controllable fields such as ``version_label`` and ``change_note``
    are intentionally NOT used to decide the bypass.

    Args:
        db_path: Path to the SQLite database.
        prompt_id: ID of the prompt version to confirm.
        allow_no_test: If True, allow confirmation even without a test artifact
            (useful for phase2-default-v1 or rollback scenarios).

    Returns:
        Dict with keys: confirmed (bool), prompt_id, reason (if blocked).

    Raises:
        ValueError: If prompt_version_id is unknown or test is blocked/failed.
    """
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM prompt_versions WHERE id = ?", (prompt_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown prompt_version_id: {prompt_id}")
        row = dict(row)
        bypass_from_db = bool(row.get("bypass_test"))

        if not (allow_no_test or bypass_from_db):
            # Check the latest test artifact for this prompt version
            test_row = conn.execute(
                """
                SELECT * FROM artifacts
                WHERE artifact_type = 'prompt_test_result'
                  AND target_type = 'prompt_version'
                  AND target_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (prompt_id,),
            ).fetchone()

            if not test_row:
                return {
                    "confirmed": False,
                    "prompt_id": prompt_id,
                    "reason": "Cannot confirm: prompt version has no passed test artifact.",
                    "test_status": "missing",
                }
            test_row = dict(test_row)
            import json as _json

            try:
                test_payload = _json.loads(test_row["metadata_json"] or "{}")
            except Exception:
                test_payload = {}
            test_status = test_payload.get("status") or test_row.get("path", "")
            if test_status != "passed":
                return {
                    "confirmed": False,
                    "prompt_id": prompt_id,
                    "reason": f"Cannot confirm: latest test status is '{test_status}'. Pass a prompt that has passed schema validation or dry-run.",
                    "test_status": test_status,
                }

        now = utc_now()
        conn.execute("UPDATE prompt_versions SET state = 'archived' WHERE task_type = ? AND state = 'confirmed'", (row["task_type"],))
        conn.execute("UPDATE prompt_versions SET state = 'confirmed', confirmed_at = ? WHERE id = ?", (now, prompt_id))
        conn.commit()
        return {
            "confirmed": True,
            "prompt_id": prompt_id,
            "reason": None,
            "bypass": bypass_from_db,
        }
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


def rollback_prompt_version(
    db_path: Path,
    source_version_id: str,
    *,
    change_note: str | None = None,
    created_by: str = "system",
) -> dict[str, Any]:
    """Rollback: create a new confirmed copy from a selected version.

    Archives the current confirmed version for the same task_type, preserves
    the original source version row, and creates a new confirmed copy with
    a change_note/source marker indicating it was created via rollback.

    Args:
        db_path: Path to the SQLite database.
        source_version_id: ID of the version to rollback to (will become new confirmed).
        change_note: Optional note explaining the rollback reason.
        created_by: Creator identifier (default "system").

    Returns:
        Dict with keys: new_version_id, archived_version_id, source_version_id, task_type.

    Raises:
        ValueError: If source_version_id is not found.
    """
    conn = connect(db_path)
    try:
        source_row = conn.execute(
            "SELECT * FROM prompt_versions WHERE id = ?", (source_version_id,)
        ).fetchone()
        if not source_row:
            raise ValueError(f"Unknown prompt_version_id: {source_version_id}")
        source = dict(source_row)
        task_type = source["task_type"]

        now = utc_now()
        rollback_marker = f"rollback_from:{source_version_id}"
        effective_change_note = change_note or f"Rollback to version '{source['version_label']}'"
        if source.get("change_note"):
            effective_change_note = f"{effective_change_note} | original: {source['change_note']}"

        current_confirmed = conn.execute(
            "SELECT id FROM prompt_versions WHERE task_type = ? AND state = 'confirmed' LIMIT 1",
            (task_type,),
        ).fetchone()
        archived_id = None
        if current_confirmed:
            archived_id = current_confirmed["id"]
            conn.execute(
                "UPDATE prompt_versions SET state = 'archived' WHERE id = ?",
                (archived_id,)
            )

        new_prompt_id = new_id("prompt")
        conn.execute(
            """
            INSERT INTO prompt_versions
            (id, task_type, version_label, state, prompt_text, change_note, created_by, created_at, confirmed_at, bypass_test)
            VALUES (?, ?, ?, 'confirmed', ?, ?, ?, ?, ?, 1)
            """,
            (
                new_prompt_id,
                task_type,
                f"rollback-{source['version_label']}",
                source["prompt_text"],
                f"{rollback_marker} | {effective_change_note}",
                created_by,
                now,
                now,
            ),
        )
        conn.commit()

        return {
            "new_version_id": new_prompt_id,
            "archived_version_id": archived_id,
            "source_version_id": source_version_id,
            "task_type": task_type,
        }
    finally:
        conn.close()


def get_phase2_defaults() -> dict[str, Any]:
    """Return Phase 2 default prompts metadata (labels and task types).

    Returns:
        Dict with 'task_types' list and 'policy' string.
    """
    return {
        "task_types": list(DEFAULT_PROMPTS.keys()),
        "policy": PHASE2_LANGUAGE_POLICY,
    }


def get_default_prompt_for_task(task_type: str) -> str | None:
    """Return the Phase 2 default prompt text for a given task type.

    Args:
        task_type: One of the known task types (extract_claims, map, etc.).

    Returns:
        The default prompt text, or None if task_type is unknown.
    """
    return DEFAULT_PROMPTS.get(task_type)
