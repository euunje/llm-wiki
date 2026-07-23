"""Phase 2 persistence helpers for review candidates and human decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect

CANDIDATE_TABLES = {
    "claim_candidates": "claim",
    "node_candidates": "node",
    "relation_candidates": "relation",
    "mapping_candidates": "mapping",
    "claim_conflict_candidates": "claim_conflict",
}


def insert_candidates_from_envelope(db_path: Path, envelope: dict[str, Any], run_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = utc_now()
    conn = connect(db_path)
    try:
        for array_field, candidate_type in CANDIDATE_TABLES.items():
            for item in envelope.get(array_field, []) or []:
                candidate_id = new_id("candidate")
                conn.execute(
                    """
                    INSERT INTO review_candidates (
                      id, candidate_type, candidate_key, source_id, run_id, payload_json,
                      review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
                    """,
                    (
                        candidate_id,
                        candidate_type,
                        item["candidate_key"],
                        envelope.get("source_id"),
                        run_id,
                        json.dumps(item, ensure_ascii=False, sort_keys=True),
                        item.get("review_route") or "normal_review",
                        item.get("review_reason") or "",
                        json.dumps(item.get("related_candidate_keys") or [], ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                rows.append({"id": candidate_id, "candidate_type": candidate_type, "candidate_key": item["candidate_key"]})
        conn.commit()
        return rows
    finally:
        conn.close()


def list_pending_candidates(db_path: Path, source_id: str | None = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if source_id:
            rows = conn.execute("SELECT * FROM review_candidates WHERE status = 'pending' AND source_id = ? ORDER BY created_at", (source_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM review_candidates WHERE status = 'pending' ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def record_retry_instruction(
    db_path: Path,
    candidate_id: str,
    *,
    reason: str,
    instruction: str,
    created_by: str = "admin",
) -> str:
    retry_id = new_id("retry")
    conn = connect(db_path)
    try:
        exists = conn.execute("SELECT 1 FROM review_candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not exists:
            raise ValueError(f"Unknown candidate_id: {candidate_id}")
        conn.execute(
            """
            INSERT INTO retry_instructions (id, target_candidate_id, reason, instruction, created_by, created_at, consumed_run_id)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (retry_id, candidate_id, reason, instruction, created_by, utc_now()),
        )
        conn.commit()
        return retry_id
    finally:
        conn.close()


def record_human_decision(
    db_path: Path,
    candidate_id: str,
    decision_type: str,
    *,
    decided_by: str = "admin",
    note: str | None = None,
    retry_instruction_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    candidate_status: str | None = None,
) -> str:
    if decision_type not in {
        "approve",
        "reject",
        "merge",
        "add",
        "create_new",
        "edit",
        "retry_with_instruction",
        "merge_into_existing",
        "link_related",
        "defer",
    }:
        raise ValueError(f"Invalid decision_type: {decision_type}")
    decision_id = new_id("decision")
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO human_decisions (id, candidate_id, decision_type, decided_by, decided_at, note, retry_instruction_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (decision_id, candidate_id, decision_type, decided_by, now, note, retry_instruction_id, json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
        )
        status = candidate_status or (
            "retry_requested"
            if decision_type == "retry_with_instruction"
            else (
                "approved"
                if decision_type in {"approve", "merge", "add", "create_new", "edit", "merge_into_existing", "link_related"}
                else ("pending" if decision_type == "defer" else "rejected")
            )
        )
        conn.execute("UPDATE review_candidates SET status = ?, updated_at = ? WHERE id = ?", (status, now, candidate_id))
        conn.commit()
        return decision_id
    finally:
        conn.close()


def supersede_candidate(db_path: Path, old_candidate_id: str, new_candidate_id: str, *, consumed_run_id: str | None = None) -> None:
    """Mark one candidate as superseded and optionally link the retry-consuming run."""
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE review_candidates SET status = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_candidate_id, now, old_candidate_id),
        )
        if consumed_run_id:
            conn.execute(
                "UPDATE retry_instructions SET consumed_run_id = ? WHERE target_candidate_id = ? AND consumed_run_id IS NULL",
                (consumed_run_id, old_candidate_id),
            )
        conn.commit()
    finally:
        conn.close()
