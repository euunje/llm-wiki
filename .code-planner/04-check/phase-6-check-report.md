# Phase 6 — Check Report

## Phase

- Phase id: `phase-6`
- Title: Test reset guide and end-to-end validation
- Source planning:
  - `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md` (Phase 6)
- Build evidence:
  - `.code-planner/03-build/evidence/phase-6-build-evidence.md`
  - `.code-planner/03-build/evidence/phase-6-test-reset-guide.md`
  - `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
  - `.code-planner/03-build/phases/phase-6-execution-brief.md`

## Changed files (this phase, on top of Phase 5B stack)

Tracked modifications (8 files, +660/-85 lines):

| File | Status | Notes |
| --- | --- | --- |
| `src/llm_wiki/cli.py` | M (+277/-7) | Phase 5B stack (+259 documented in `phase-5B-build-evidence.md`) plus Phase 6 archive-finalization wiring (UUID import, `_inbox_state_counts`, `_linked_inbox_item_for_source`, two `_finalize_successful_inbox_ingest` call sites). |
| `src/llm_wiki/inbox.py` | M (+84/-0) | Phase 6 archive-finalization deliverable: `finalize_successful_ingest` and the supporting `_is_within_directory` helper. This was added during Phase 6 to unblock E2E rows B-7 / C-3. |
| `src/llm_wiki/jobs.py` | M (+51/-3) | Phase 5B stack (+26) plus Phase 6 `JobManager._run_job` success path calling `finalize_successful_ingest` for the linked inbox item. |
| `src/llm_wiki/webapp/routes/ingest.py` | M (+37/-3) | Pure Phase 5B stack. |
| `src/llm_wiki/webapp/templates/ingest.html` | M (+80/-31) | Pure Phase 5B stack. |
| `src/llm_wiki/webapp/templates/jobs.html` | M (+3/-1) | Pure Phase 5B stack. |
| `tests/test_inbox_to_job_mapping.py` | M (+106/-0) | Phase 5B stack plus Phase 6 archive-finalization regression test `test_background_job_success_finalizes_linked_inbox_item_into_raw_archive`. |
| `tests/test_web_navigation.py` | M (+107/-40) | Pure Phase 5B stack. |

Untracked:

- `.code-planner/` — Phase 6 evidence + Phase 5B evidence + PRV artifacts. In scope.
- `.prv/` — pre-existing PRV review artifacts (out of scope, unrelated).
- `tests/test_cli_inbox.py` — Phase 5B test file; in scope.

## Affected flow

Phase 6 added the missing **archive-finalization** step on successful ingest:

1. CLI success route — `cli.ingest <no arg>` and `cli.ingest <source_id>` (linked-item branch):
   - `_process_inbox_item` (or the source_id branch) calls `ingest_llm.ingest_source`.
   - On `result.ok`, calls `_finalize_successful_inbox_ingest` → `inbox.finalize_successful_ingest` with `event_type='cli_ingest_completed'`.
   - On `result.skipped` / error, the prior `_set_inbox_item_state` path keeps PENDING / FAILED with `cli_ingest_skipped` / `cli_ingest_failed` events.
2. Web / job route — `/ingest/start` → `JobManager.enqueue` → `JobManager._run_job`:
   - After `ingest_llm.ingest_source` returns `result.ok`, the worker resolves the linked inbox item via `_linked_inbox_item_id_for_source` and calls `inbox.finalize_successful_ingest` with `event_type='job_ingest_completed'`, passing `data={'job_id': job_id, 'requested_via': 'job'}`.
   - The legacy source-only ingest (no linked item) is unchanged.
3. `inbox.finalize_successful_ingest`:
   - Reads the current inbox item + source row.
   - If the file is already under `paths.raw_archive` (idempotent path), it reuses the existing archive copy.
   - Otherwise calls `move_to_archive(...)` which moves the file from `Inbox/<type>/<name>` to `raw/<name>` via `_safe_copy_or_move`.
   - Updates `sources.relpath` to the new raw relpath.
   - Transitions the inbox item to `INGESTED` with `moved_to_archive` event followed by the final completion event.
4. The old CLI / job paths previously only updated `sources.status='ingested'` and the inbox item state; they did not move the original file or record `moved_to_archive`. That gap is what Phase 6 closes.

## Required check results

### 변경 범위 검사 (change scope)

- Verdict from `check-change-scope`: scope drift detected but contained.
- All 8 modified files are aligned with either Phase 5B stack or the Phase 6 archive-finalization fix.
- No unrelated drift; no `.env` / secrets / build outputs; no `rm -rf` introduced.
- The drift flagged by the subagent is purely documentation: `phase-6-build-evidence.md` previously stated "No code was changed in Phase 6" and Phase 5B evidence said "No modifications to inbox.py". Both statements are now stale and must be corrected in a follow-up evidence patch (see fix request CHK-001 below). It does not block the gate functionally — the code itself is correct and tests are green.

### 영향 흐름 검사 (affected flow)

- Verified by direct read of `src/llm_wiki/inbox.py:963-1036`, `src/llm_wiki/cli.py:147-264, 815-922`, `src/llm_wiki/jobs.py:252-258, 536-548`.
- The finalize step is centralized in `inbox.finalize_successful_ingest` and is called from both CLI and job flows with explicit `event_type` so audit trail differentiates them.
- Legacy source-only ingest (`wiki ingest <source_id>` with no linked inbox item) is preserved.

### 기능 완성도 검사 (feature completeness)

- E2E rows now passing in evidence:
  - A-1, A-3, A-4, A-5 pass; A-6 registration-only.
  - B-2 markdown success route pass (with `/v1` host fix).
  - B-3 pasted text success route pass.
  - B-7 Raw archive movement pass (after archive finalization fix).
  - C-1 Wiki page create pass.
  - C-3 Raw archive movement pass.
- E2E rows still pending:
  - A-2 duplicate registration.
  - B-1 document file success route (tested and failed earlier; not re-exercised after the archive fix; the failed fixture is `sample-doc.txt` which remains `failed`).
  - B-4 chunked extraction, B-5 failed route, B-6 review route, B-8 existing Raw import processing.
  - C-2 update re-ingest.
  - D-1/D-2/D-3 operator workbench checks.
  - E-1/E-2/E-3/E-4 edge cases.
- The fix request CHK-001 (STAB-002) covers the cli ingest source_id+linked-item coverage gap.
- Phase 6 scope itself (test reset guide + E2E matrix + this archive fix) is functionally complete to the extent defined by `phase-6-test-reset-validation.md`. The remaining pending rows are operator-runnable and explicitly called out in the build evidence as not blocking the close.

### 안정성 검사 (stability)

- Verdict from `check-code-stability`: pass-with-notes.
- STAB-001 (note): `JobManager._worker_loop` broad `except Exception` will overwrite `state='done'` with `state='failed'` if `finalize_successful_ingest` throws after wiki pages are written. Latent; not a regression. Recorded as an acceptance criterion for the fix request.
- STAB-002 (medium, fixable): no automated test for `cli.ingest <source_id>` with a linked inbox item. Required: add a new test in `tests/test_cli_inbox.py` mirroring the existing `_process_inbox_item` happy-path test but entering via `source_id`. See fix request CHK-001.
- STAB-003 (low): near-duplicate linked-inbox lookup query in `cli.py` and `jobs.py`. Cosmetic; not blocking.
- STAB-004 (note): orphaned lowercase sentence in `cli.ingest` docstring at `src/llm_wiki/cli.py:815-817`. Cosmetic.
- STAB-005 to STAB-008: notes only; no action required.

### 유지보수성 검사 (maintainability)

- Centralized archive finalization in `inbox.finalize_successful_ingest` is the right level of abstraction — both CLI and job flows delegate to it.
- `event_type` is parameterized so downstream audit (`inbox_events`) and any future reporting can distinguish `cli_ingest_completed` vs `job_ingest_completed`.
- Sources relpath is updated to point at the raw archive, so wiki frontmatter `source_path` references stay consistent after archive.
- No new long-lived listeners; no new threads; `ps`/`ss` snapshot clean.
- STAB-004 (orphaned docstring) and STAB-003 (duplicate query) are minor; can be cleaned up in the same fix request.

### 보안/설정 검사 (security/config)

- No `.env` / secret files in the diff. Real LLM E2E runs loaded the existing `~/.hermes/.env` keys via `os.environ` in the harness; no secret values were printed.
- `cli.retry` diagnostic-sidecar deletion is `Path.unlink` only — non-recursive, scoped to a deterministic sibling path. No `rm -rf`, no glob deletion.
- Ollama default host `http://localhost:11434` only used as OOBE default; runtime always overrides via `llm_cfg.get('host', ...)`. No new hardcoded URLs.
- No new config/dependency/env changes in the tracked diff.
- No build outputs / cache artifacts present.

### 검증 증거 검사 (verification evidence)

- `tests/test_inbox_to_job_mapping.py::test_background_job_success_finalizes_linked_inbox_item_into_raw_archive` — exercises the new finalize path on the job side.
- `tests/test_cli_inbox.py::test_ingest_processes_pending_inbox_items_via_materialization_path` — exercises the new finalize path on the CLI side via `_process_inbox_item`.
- `tests/test_cli_inbox.py::test_ingest_source_id_without_linked_inbox_item_keeps_legacy_raw_source` — legacy source-only branch unchanged.
- Focused pytest (this check session): `43 passed, 1 warning in 15.42s`.
  - `tests/test_web_navigation.py` 9 passed
  - `tests/test_inbox_to_job_mapping.py` 6 passed (incl. new archive test)
  - `tests/test_inbox_domain.py` 4 passed
  - `tests/test_inbox_registration.py` 16 passed
  - `tests/test_phase4_review_failed_workbench.py` 4 passed
  - `tests/test_cli_inbox.py` 4 passed
- `py_compile` on changed files: exit 0.
- `git diff --check`: exit 0.
- `ps -ef | grep -E "(uvicorn|pytest|llm_wiki|wiki)"`: no matching processes.
- Real LLM E2E (existing ENV, `/v1` host correction, openai-local): pasted-text fixture ingested end-to-end with archive movement, ingested state, sources relpath aligned. Log: `/tmp/opencode/phase6-llm-ingest-paste-v1-archive-fix.log`.

## Convention result

- Commits kept stacked on `29e4808` (Phase 5A) per the user's standing instruction "do not commit until the current full work is complete". This applies to Phase 5B and Phase 6.
- Documentation artifacts live under `.code-planner/` and are untracked, consistent with the planning-artifact convention used in earlier phases.
- No `.prv/` commits and no edits to that directory (it is pre-existing review/IDE output).

## Code stability result

- `check-code-stability`: pass-with-notes.
- See fix request CHK-001 for the actionable STAB-002 coverage gap.
- Notes STAB-001 / STAB-003 / STAB-004 are recorded for follow-up but do not block the gate.

## Implementation completeness

- Phase 6 scope per `phase-6-test-reset-validation.md` and `phase-6-execution-brief.md`:
  - One-time test reset guide: delivered (`phase-6-test-reset-guide.md`).
  - E2E validation checklist: delivered (`phase-6-e2e-validation-checklist.md`).
  - Automated non-destructive validation pass: delivered (`phase-6-build-evidence.md` §"Non-destructive validation commands").
  - Archive finalization (Phase 6 code in-flight to unblock E2E): delivered (`inbox.finalize_successful_ingest` + CLI/job wiring + tests).
- No new product UX surface was introduced. Visual UX remains delegated to Phase 5B user-test-checklist (`P-2`).

## User functional test required

- `check-user-test`: required = **no**.
- Phase 6 introduces no new visible UX elements. Visual UX sign-off is delegated to `.code-planner/04-check/phase-5B-user-test-checklist.md`.
- The operator-driven rows in the E2E matrix are not user functional tests in the check-main sense; they are validation runs that require a real LLM endpoint and operator interaction. The user has authorized the existing ENV / LLM E2E for this phase.

## User test result or approval state

- No new user-test checklist required. Existing Phase 5B user-test checklist (`phase-5B-user-test-checklist.md`) remains authoritative and unchanged.
- Real LLM E2E approved by user (existing ENV used). Operator results recorded in `phase-6-e2e-validation-checklist.md`.

## Git final verification result

- `git status --short`: 8 tracked modified, 3 untracked (`.code-planner/`, `.prv/`, `tests/test_cli_inbox.py`).
- `git diff --stat HEAD`: 8 files / +660/-85.
- `git diff --check`: clean.
- No `.env` / secret / cache / build outputs included.
- Lint/format/test/build evidence: pytest 43 passed, py_compile clean.
- User functional test requirement: none (per `check-user-test`).
- Commits: **deferred** per user instruction. No commit will be created at this gate; see "Commit policy" below.

## Commit policy

- No commit produced at this gate. Reason: user instructed not to commit until the current full work is complete (Phase 5B + Phase 6 stacked + archive finalization patch).
- The intended commit boundary when the user releases the hold is described in "Required follow-ups".

## Required follow-ups (non-blocking at this gate, tracked in fix request)

See `.code-planner/04-check/fix-requests/phase-6-fix-request.md`:

1. **CHK-001 (medium, fixable)** — `cli.ingest <source_id>` with a linked inbox item lacks an automated regression test. Add a new test in `tests/test_cli_inbox.py` that mirrors `test_ingest_processes_pending_inbox_items_via_materialization_path` but enters via `source_id` after `materialize_source_for_inbox_item`. Acceptance: pytest passes; coverage of the cli.py:863-909 linked-item branch is established.
2. **CHK-002 (low)** — Update `.code-planner/03-build/evidence/phase-6-build-evidence.md` to correct the "No code was changed in Phase 6" claim and to document the archive-finalization code path. Update `.code-planner/03-build/evidence/phase-5B-build-evidence.md` to note that `inbox.py` was later modified as a Phase 6 prerequisite.
3. **CHK-003 (note)** — Optional cleanup: address STAB-003 (`linked_inbox_item_id_for_source` shared helper) and STAB-004 (orphaned docstring sentence) in a follow-up.

## Gate result

```text
source_validated_commit_deferred
```

Rationale:
- Functional scope of Phase 6 is complete (test reset guide, E2E matrix, archive finalization, evidence).
- CHK-001 / CHK-002 / CHK-003 were addressed by `WU-P6-FIX-CHK123` and recorded in `.code-planner/03-build/evidence/phase-6-fix-evidence.md`.
- No user functional test required, no security/config blockers, no unrelated drift.
- Commit remains deferred only because the user instructed not to commit until the current full work is complete.

## Commit hash

- (none — commit deferred by user instruction)

## Post-fix recheck addendum

After the initial `changes_requested` verdict, the user approved applying the three lightweight fixes immediately. The Build fix pass `WU-P6-FIX-CHK123` closed all requested items:

| Fix request | Status | Evidence |
| --- | --- | --- |
| CHK-001 — add regression coverage for `wiki ingest <source_id>` with a linked inbox item | closed | `tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state`; `.code-planner/03-build/evidence/phase-6-fix-evidence.md` |
| CHK-002 — correct Phase 6 / Phase 5B evidence to acknowledge archive-finalization code changes | closed | `.code-planner/03-build/evidence/phase-6-build-evidence.md`; `.code-planner/03-build/evidence/phase-5B-build-evidence.md` |
| CHK-003 — low-cost maintainability cleanup | closed | `inbox.linked_inbox_item_id_for_source(...)`; CLI/jobs delegation; `cli.ingest` docstring cleanup |

Post-fix verification:

- `pytest tests/test_cli_inbox.py tests/test_inbox_to_job_mapping.py -q`: **11 passed, 1 warning**.
- Full focused pytest (`test_web_navigation`, `test_inbox_to_job_mapping`, `test_inbox_domain`, `test_inbox_registration`, `test_phase4_review_failed_workbench`, `test_cli_inbox`): **44 passed, 1 warning**.
- `py_compile` on touched source/test files: **exit 0**.
- `git diff --check`: **exit 0**.
- Process/port cleanup: no `uvicorn` / `pytest` / `llm_wiki` / `wiki` process left running by the fix pass.

Updated git final verification after CHK fixes:

- `git status --short`: 8 tracked modified, 3 untracked (`.code-planner/`, `.prv/`, `tests/test_cli_inbox.py`).
- `git diff --stat HEAD`: 8 files changed, **674 insertions(+), 85 deletions(-)**.
- No `.env` / secret / dependency / config file leakage detected.

Final post-fix gate:

```text
source_validated_commit_deferred
```

Reason: all check-main fix requests are closed and validation is green, but commit is still intentionally deferred by the user's standing instruction.
