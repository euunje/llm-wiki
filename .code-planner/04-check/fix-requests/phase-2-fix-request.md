# Phase 2 Fix Request

| Field | Value |
| --- | --- |
| Phase | 2 — LLM Wiki Quality |
| Source check report | `.code-planner/04-check/phase-2-check-report.md` |
| Build verdict | `changes_requested` |

Each fix request follows the standard schema:

```text
id
short title
problem target
reason
improvement spec
suggested build agent
validation required
acceptance criteria
```

---

## STAB-001 — HTML/URL ingest failure artifacts are dropped

- **id:** STAB-001
- **short title:** HTML/URL ingest drops structured failure artifacts
- **problem target:**
  - `src/llm_wiki/pipeline/ingest.py` (HTML branch `convert_input` failure path; URL branch)
  - `src/llm_wiki/pipeline/convert.py` (`ConversionResult.artifact_payload`)
- **reason:** The HTML converter adapter already produces a structured `ConversionResult.artifact_payload` with type/reason/path, but `ingest.ingest_markdown_file` discards it and only raises `UnsupportedInputError`. The URL branch raises without recording any artifact. Phase 2 contract requires explicit failure artifacts for traceability.
- **improvement spec:**
  - In `ingest_markdown_file`, before raising on `convert_input` failure, call `jobs.record_artifact(workspace, artifact_type="ingest_conversion_error", task_type="ingest", payload=result.artifact_payload, target_type="source_path", target_id=str(path))`.
  - For URL branch, synthesize a minimal artifact payload (`{reason, type: "url_unsupported", path: input_str}`) and call the same `record_artifact` helper before raising.
- **suggested build agent:** build-backend-script-dev
- **validation required:**
  - Unit test: ingest a malformed `.html` body returns exit 2 AND writes an `ingest_conversion_error` artifact under `data/artifacts/ingest/<sanitized>/<run_id>.json`.
  - Unit test: ingest a URL string returns exit 2 AND writes a `url_unsupported` artifact.
- **acceptance criteria:**
  - Both tests pass.
  - No new mandatory dependency.
  - Phase 1 tests remain green.

---

## STAB-002 — Retry path does not populate `consumed_run_id`

- **id:** STAB-002
- **short title:** Retry on a candidate target does not mark `retry_instructions.consumed_run_id`
- **problem target:**
  - `src/llm_wiki/cli/ops_cmds.py` `run_retry` (candidate branch)
  - `src/llm_wiki/schema/review.py` `supersede_candidate`
- **reason:** `retry_instructions.consumed_run_id` is a documented audit column but is never set in the current candidate retry flow. The DB column always stays NULL even though the schema exposes it.
- **improvement spec:**
  - In `run_retry` candidate branch, pass the new candidate's `run_id` to `supersede_candidate(workspace.db, args.target_id, superseded_by, consumed_run_id=new_run_id)` when a follow-up run was just inserted in this flow.
  - If no follow-up run is produced, leave the column NULL and add a docstring on `supersede_candidate` clarifying that callers must provide `consumed_run_id` when one exists.
- **suggested build agent:** build-core-dev
- **validation required:**
  - Add a unit test that after a candidate retry, `retry_instructions.consumed_run_id` is populated with the follow-up run id (when applicable).
- **acceptance criteria:**
  - Test passes.
  - Phase 1 tests remain green.
  - No new mandatory dependency.

---

## STAB-003 — Forbidden-key check does not recurse into nested objects

- **id:** STAB-003
- **short title:** `validate_candidate_envelope` does not recurse for forbidden keys
- **problem target:**
  - `src/llm_wiki/schema/candidates.py` `validate_candidate_envelope`, `_validate_ref`, `_validate_evidence`
- **reason:** Forbidden LLM keys (`human_decision`, `retry_instruction`, `approved`, `rejected`, `replaced`) are checked only at envelope top level and item top level. Nested structures (`subject_ref`, `object_ref`, `source_ref`, `target_ref`, `incoming_ref`, `evidence[]`, `locator`, `qualifiers`) are not scanned. A crafted envelope can smuggle `human_decision` into `subject_ref` and pass validation.
- **improvement spec:**
  - Add a recursive walk that collects forbidden keys at any depth inside the envelope payload.
  - Call the walk from `validate_candidate_envelope` before per-type field validation, so the report surfaces the exact nested path.
  - Add a unit test that sets `node_candidates[0]["subject_ref"]["human_decision"] = {}` and asserts `validation.ok is False` with a `forbidden` error referencing the nested path.
- **suggested build agent:** build-core-dev
- **validation required:**
  - New unit test in `tests/test_phase2_schema_quality.py`.
  - `PYTHONPATH=src python3 -m tests.run_phase1` and `PYTHONPATH=src python3 -m tests.run_phase2` both pass.
- **acceptance criteria:**
  - Test passes.
  - Existing positive test (`test_phase2_candidate_schema_accepts_title_mapping_contract`) still passes.

---

## STAB-004 — Module docstrings are inconsistent on new Phase 2 modules

- **id:** STAB-004
- **short title:** Module docstrings inconsistent across Phase 2 modules
- **problem target:**
  - `src/llm_wiki/quality.py`
  - `src/llm_wiki/schema/candidates.py`
  - `src/llm_wiki/schema/prompts.py`
  - `src/llm_wiki/schema/review.py`
  - `src/llm_wiki/search/vector.py`
  - `src/llm_wiki/search/__init__.py`
- **reason:** Phase 2 brief expects consistent module-level headers. `pipeline/convert.py` has a 21-line docstring; the other new Phase 2 modules start with `from __future__ import annotations` and have no header.
- **improvement spec:**
  - Add a short module docstring (≤6 lines) to each listed file, describing its Phase 2 contract boundary, mirroring the tone of `pipeline/convert.py`.
- **suggested build agent:** build-core-dev
- **validation required:**
  - `PYTHONPATH=src python3 -m compileall -q src tests` passes.
  - All test runners pass.
- **acceptance criteria:**
  - Every listed file has a module docstring.

---

## Notes

- STAB-005..STAB-011 are low-severity and may be addressed in the same fix pass or the next Phase 2 recheck.
- Build must not commit until these issues are addressed and `check-git-final` passes.
