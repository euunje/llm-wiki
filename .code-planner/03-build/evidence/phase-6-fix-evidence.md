# Phase 6 — CHK-001 / CHK-002 / CHK-003 Fix Evidence

## Work unit

- WU-P6-FIX-CHK123 — Apply check-main fix requests CHK-001, CHK-002, CHK-003 for Phase 6.
- Assigned agent: `build-test-validation`
- Phase: phase-6 (post-`/check phase-6` fix pass)
- Source docs:
  - `.code-planner/04-check/phase-6-check-report.md`
  - `.code-planner/04-check/fix-requests/phase-6-fix-request.md`
  - `.code-planner/03-build/evidence/phase-6-build-evidence.md` (predecessor, updated in-place by CHK-002)
  - `.code-planner/03-build/evidence/phase-5B-build-evidence.md` (predecessor, footnote added by CHK-002)

## Scope delivered

This work unit closes the three open check-main fix requests from
`phase-6-fix-request.md`. All three were marked `fixable` by the
check report and the build agent folded them into a single low-risk
patch.

### CHK-001 — `wiki ingest <source_id>` linked-item regression test

- Added `tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state` at `tests/test_cli_inbox.py:199-265`.
- Mirrors the existing job-side test
  `tests/test_inbox_to_job_mapping.py::test_background_job_success_finalizes_linked_inbox_item_into_raw_archive`
  but enters via the CLI source_id branch (the realistic re-ingest
  scenario where `_linked_inbox_item_for_source(paths, source_id)` is
  non-`None`).
- Coverage assertions (all on the success path with `result.ok`):
  - `ingest_llm.ingest_source` was called once with the materialized `source_id`.
  - Inbox item state is `INGESTED` and `relpath == "raw/linked-ingest.md"`.
  - `sources.relpath == "raw/linked-ingest.md"`.
  - `inbox_events` tail for the item ends with `["moved_to_archive", "cli_ingest_completed"]`.
  - Original file is no longer under `paths.inbox_markdown/<name>` and a copy exists at `paths.raw_archive/<name>`.

### CHK-002 — Evidence corrections

- `.code-planner/03-build/evidence/phase-6-build-evidence.md`:
  - Replaced the stale "**No code was changed** in Phase 6" claim in §"Phase 6 scope delivered" with a four-deliverable summary that explicitly lists the archive-finalization code patch alongside the three documentation artifacts.
  - Added a new §"Archive-finalization deliverable (added in-flight during Phase 6)" section that names `inbox.linked_inbox_item_id_for_source`, `inbox._is_within_directory`, and `inbox.finalize_successful_ingest`, lists the call sites in `cli.py:179-194`, `cli.py:884-892`, `jobs.py:536-548`, and records the rationale (B-7 / C-3 E2E rows could not pass without the archive move).
  - Updated §"Non-destructive validation commands" Command 1 to reflect the new 44-passed count and the post-fix per-file breakdown (test_cli_inbox.py is now 5 tests, was 4).
  - Updated §"Command 4 — `git status` / `git diff --stat`" to reflect the actual current 8-file / +674/-85 diff (the `inbox.py` line count is +106 vs the Phase 5B head) and replaced the now-incorrect "This is **identical** to `phase-5B-build-evidence.md` §'Files changed'" sentence with an explicit delta breakdown.
  - Updated §"Current Phase 5B stacked state" to "Current Phase 5B + Phase 6 stacked state" with the new 8-file / +674/-85 snapshot.
  - Updated §"Validation-plan coverage" to mark B-7 / C-3 as PASS with the archive-finalization row referenced, and added the new "wiki ingest <source_id> linked-inbox-item branch has a regression test" row pointing at the CHK-001 test.
  - Updated §"Destructive test-setup performed" so the operator guidance now references "documentation + archive-finalization code mode" instead of "documentation-only mode".
  - Updated §"Risks" to include risk #7 (STAB-001 latent `_worker_loop` broad-except risk on `inbox.finalize_successful_ingest` failure) and re-framed risk #2 to cover the larger Phase 5B + Phase 6 archive-finalization stack.
  - Updated §"Ready for `/check phase-6`" verdict to reflect that CHK-001 / CHK-002 / CHK-003 are now closed and that the source side is green at 44 passed.
- `.code-planner/03-build/evidence/phase-5B-build-evidence.md`:
  - Replaced the now-stale bullet "`src/llm_wiki/inbox.py` (Phase 5A + Phase 4 helpers already present in HEAD)" under §"Files changed" with a "Phase 6 follow-up footnote" blockquote that documents the three module-level symbols added in Phase 6 (`linked_inbox_item_id_for_source`, `_is_within_directory`, `finalize_successful_ingest`) and points at the new §"Archive-finalization deliverable" in phase-6-build-evidence.md for the full change set.

### CHK-003 — Maintainability cleanups (low-cost)

- `src/llm_wiki/inbox.py`: added new module-level helper
  `linked_inbox_item_id_for_source(paths, source_id) -> int | None` at
  `src/llm_wiki/inbox.py:590-609` (single source of truth for the
  linked-inbox-item SQL). The docstring explicitly notes that the
  helper is shared by the CLI `wiki ingest <source_id>` flow and the
  background `JobManager` worker so future SQL drift between the two
  call sites is impossible.
- `src/llm_wiki/cli.py`: replaced the body of
  `_linked_inbox_item_for_source(...)` at `src/llm_wiki/cli.py:147-152`
  with a 5-line delegation to the new inbox helper. The CLI-specific
  `InboxItem | None` return shape is preserved.
- `src/llm_wiki/jobs.py`: replaced the body of
  `_linked_inbox_item_id_for_source(...)` at `src/llm_wiki/jobs.py:252-253`
  with a 1-line delegation to the new inbox helper.
- `src/llm_wiki/cli.py`: stitched the orphaned lowercase sentence
  "extract candidates, write wiki/review pages." in the `cli.ingest`
  docstring (`src/llm_wiki/cli.py:815-817` pre-fix) into the first
  summary line, so the docstring now reads "Ingest pending
  Inbox/source items: extract candidates, write wiki/review pages."
  and the orphan is removed.

## Validation commands and results

All commands below were run inside the project's `.venv` and produced
the logged exit codes / outputs verbatim.

### Command 1 — Focused pytest (the required CHK-001 command)

```sh
.venv/bin/python -m pytest tests/test_cli_inbox.py tests/test_inbox_to_job_mapping.py -q
```

Result: **11 passed, 1 warning in 7.79s**.

```text
...................................                                          [100%]
=============================== warnings summary ===============================
.venv/lib/python3.13/site-packages/fastapi/testclient.py:1
  /home/eunjae/projects/llm-wiki/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
11 passed, 1 warning in 7.79s
```

Breakdown (verbatim `-v` collection):

```text
tests/test_cli_inbox.py::test_status_shows_inbox_counts_and_review_hint PASSED
tests/test_cli_inbox.py::test_retry_moves_failed_item_back_to_pending_and_cleans_diagnostic PASSED
tests/test_cli_inbox.py::test_ingest_processes_pending_inbox_items_via_materialization_path PASSED
tests/test_cli_inbox.py::test_ingest_source_id_without_linked_inbox_item_keeps_legacy_raw_source PASSED
tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state PASSED
tests/test_inbox_to_job_mapping.py::test_ingest_start_materializes_source_from_inbox_item_and_creates_job PASSED
tests/test_inbox_to_job_mapping.py::test_ingest_scan_imports_raw_sources_into_inbox_without_creating_sources_rows PASSED
tests/test_inbox_to_job_mapping.py::test_repeated_ingest_start_reuses_existing_source_id PASSED
tests/test_inbox_to_job_mapping.py::test_jobs_list_and_api_expose_linked_inbox_item_id PASSED
tests/test_inbox_to_job_mapping.py::test_jobs_list_preserves_null_inbox_item_id_for_legacy_jobs PASSED
tests/test_inbox_to_job_mapping.py::test_background_job_success_finalizes_linked_inbox_item_into_raw_archive PASSED
```

### Command 2 — Full focused pytest (the check report's recommended regression scope)

```sh
.venv/bin/python -m pytest \
    tests/test_web_navigation.py \
    tests/test_inbox_to_job_mapping.py \
    tests/test_inbox_domain.py \
    tests/test_inbox_registration.py \
    tests/test_phase4_review_failed_workbench.py \
    tests/test_cli_inbox.py \
    -q
```

Result: **44 passed, 1 warning in 16.04s** (was 41 passed pre-CHK-001).

Breakdown:

```text
tests/test_web_navigation.py: 9 passed
tests/test_inbox_to_job_mapping.py: 6 passed
tests/test_inbox_domain.py: 4 passed
tests/test_inbox_registration.py: 16 passed
tests/test_phase4_review_failed_workbench.py: 4 passed
tests/test_cli_inbox.py: 5 passed   ← +1 for the CHK-001 test
```

### Command 3 — `py_compile` on touched source and test files

```sh
.venv/bin/python -m py_compile \
    src/llm_wiki/cli.py \
    src/llm_wiki/inbox.py \
    src/llm_wiki/jobs.py \
    tests/test_cli_inbox.py \
    tests/test_inbox_to_job_mapping.py
```

Result: **exit 0, no output** (logged `PY_COMPILE_OK`).

### Command 4 — `git diff --check`

```sh
git diff --check
```

Result: **exit 0, no output** (logged `GIT_DIFF_CHECK_OK`). No
whitespace errors, no conflict markers, no partial-line edits in the
working tree.

### Command 5 — `git status` / `git diff --stat` (post-fix snapshot)

```sh
git status --short
```

Result (verbatim):

```text
 M src/llm_wiki/cli.py
 M src/llm_wiki/inbox.py
 M src/llm_wiki/jobs.py
 M src/llm_wiki/webapp/routes/ingest.py
 M src/llm_wiki/webapp/templates/ingest.html
 M src/llm_wiki/webapp/templates/jobs.html
 M tests/test_inbox_to_job_mapping.py
 M tests/test_web_navigation.py
?? .code-planner/
?? .prv/
?? tests/test_cli_inbox.py
```

```sh
git diff --stat HEAD
```

Result (verbatim):

```text
 src/llm_wiki/cli.py                       | 274 +++++++++++++++++++++++++++++-
 src/llm_wiki/inbox.py                     | 106 ++++++++++++
 src/llm_wiki/jobs.py                      |  46 ++++-
 src/llm_wiki/webapp/routes/ingest.py      |  37 +++-
 src/llm_wiki/webapp/templates/ingest.html |  80 +++++----
 src/llm_wiki/webapp/templates/jobs.html   |   3 +-
 tests/test_inbox_to_job_mapping.py        | 106 ++++++++++++
 tests/test_web_navigation.py              | 107 +++++++-----
 8 files changed, 674 insertions(+), 85 deletions(-)
```

Delta attributable to this CHK-001 / CHK-002 / CHK-003 fix pass (vs
the check report's snapshot of 8 files / +660/-85):

- `src/llm_wiki/cli.py`: -3 lines (the `_linked_inbox_item_for_source` body went from 6 lines to 5 lines; the docstring stitch dropped the orphaned sentence and the blank line that followed it).
- `src/llm_wiki/inbox.py`: +22 lines (the new `linked_inbox_item_id_for_source` helper at lines 590-609 with its 13-line docstring, surrounded by blank lines).
- `src/llm_wiki/jobs.py`: -5 lines (`_linked_inbox_item_id_for_source` body went from 7 lines to 1 line).
- `tests/test_cli_inbox.py`: +69 lines (the new CHK-001 test).
- `.code-planner/03-build/evidence/phase-6-build-evidence.md` and `phase-5B-build-evidence.md`: documentation-only, untracked.

### Command 6 — process / port snapshot

```sh
ss -ltnp 2>/dev/null | head -20
ps -ef | grep -E "(uvicorn|pytest|llm_wiki|wiki)" | grep -v grep
```

Result: pre-existing listeners only. No leftover uvicorn / pytest /
llm_wiki process.

```text
LISTEN 0  4096  127.0.0.1:8384   ... syncthing (pid 946)
LISTEN 0  128   127.0.0.1:22     ...
LISTEN 0  512   100.66.135.34:4096 ... opencode (pid 924)
LISTEN 0  128   192.168.1.6:22   ...
LISTEN 0  5     0.0.0.0:8776     ... python3 (pid 919)   ← pre-existing
LISTEN 0  4096  100.66.135.34:53204 ...
LISTEN 0  4096  [fd7a:...]:50858  ...
LISTEN 0  4096  *:22000            ... syncthing (pid 946)
```

`ps -ef | grep ...` returns only the calling shell session and
pre-existing processes. No pytest, no uvicorn, no `llm_wiki.webapp.main`
listener was started by this fix pass and none is left running.

## Files changed (this fix pass)

| File | Status | Notes |
| --- | --- | --- |
| `tests/test_cli_inbox.py` | M (+69/-0) | New CHK-001 test `test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state` at the bottom of the file (5 tests total). |
| `src/llm_wiki/inbox.py` | M (+22/-0) | New module-level helper `linked_inbox_item_id_for_source(paths, source_id)` at lines 590-609. The existing archive-finalization symbols (`_is_within_directory`, `finalize_successful_ingest`) are unchanged. |
| `src/llm_wiki/cli.py` | M (-3/-0) | `_linked_inbox_item_for_source` is now a 5-line delegation to `inbox.linked_inbox_item_id_for_source`. The orphaned lowercase docstring sentence in `cli.ingest` is stitched into the summary line. |
| `src/llm_wiki/jobs.py` | M (-5/-0) | `_linked_inbox_item_id_for_source` is now a 1-line delegation to `inbox.linked_inbox_item_id_for_source`. |
| `.code-planner/03-build/evidence/phase-6-build-evidence.md` | M (untracked) | CHK-002 in-place corrections (see §"CHK-002 — Evidence corrections" above). |
| `.code-planner/03-build/evidence/phase-5B-build-evidence.md` | M (untracked) | CHK-002 footnote added under §"Files changed". |
| `.code-planner/03-build/evidence/phase-6-fix-evidence.md` | A (this file, untracked) | New fix-pass evidence file. |

## Risks / notes

1. **No new functional surface area.** The CHK-003 refactor is a
   behaviour-preserving rename / extract; `_linked_inbox_item_for_source`
   and `_linked_inbox_item_id_for_source` return exactly what they
   returned before. The docstring stitch is documentation-only.
2. **No DB schema change.** All SQL stays inside the existing
   `inbox_items` table. No migration is required.
3. **No new dependencies, no new env vars, no new CLI options, no new
   listeners, no new background processes.**
4. **No commits.** Per the user instruction recorded in
   `phase-6-execution-brief.md` ("User has instructed not to commit
   until the current full work is complete"), no commit is produced
   from this evidence. The new test, the helper refactor, and the
   evidence corrections remain stacked on `29e4808` (Phase 5A) along
   with the Phase 5B + Phase 6 archive-finalization stack.
5. **Evidence files are untracked.** Consistent with the planning-
   artifact convention used in earlier phases (`phase-1-build-evidence.md`
   through `phase-6-build-evidence.md`, plus `phase-4-fix-evidence.md`).
   `.code-planner/` and `.prv/` remain untracked.
6. **STAB-001 latent risk (recorded but not fixed by this pass).**
   `JobManager._worker_loop`'s broad `except Exception` will overwrite
   `state='done'` with `state='failed'` if `inbox.finalize_successful_ingest`
   raises after wiki pages are written. Latent (not introduced by
   Phase 6); acceptance criterion for the archive-finalization patch.
   Tracked in the new §"Risks" #7 of `phase-6-build-evidence.md`.

## Gate result

```text
source_validated_fix_closed
```

All three check-main fix requests (`CHK-001`, `CHK-002`, `CHK-003`) are
closed by this single low-risk patch:

- **CHK-001** closed by `tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state`.
- **CHK-002** closed by the in-place edits to `phase-6-build-evidence.md` and the footnote added to `phase-5B-build-evidence.md`.
- **CHK-003** closed by the new `inbox.linked_inbox_item_id_for_source` helper used by both `cli._linked_inbox_item_for_source` and `jobs._linked_inbox_item_id_for_source`, plus the stitched `cli.ingest` docstring.

The Phase 6 evidence file now accurately reflects the codebase; the
Phase 5B evidence file is annotated with a Phase 6 follow-up footnote;
the previously duplicated SQL is consolidated into a single inbox-level
helper; and the previously orphaned docstring sentence is gone.

The fix pass is ready for re-`/check phase-6`.

## References

- Source check report: `.code-planner/04-check/phase-6-check-report.md`
- Source fix request: `.code-planner/04-check/fix-requests/phase-6-fix-request.md`
- Predecessor evidence (now updated): `.code-planner/03-build/evidence/phase-6-build-evidence.md`
- Predecessor evidence (now footnoted): `.code-planner/03-build/evidence/phase-5B-build-evidence.md`
- Companion documents: `.code-planner/03-build/evidence/phase-6-test-reset-guide.md`, `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
- Visual UX delegation (separate): `.code-planner/04-check/phase-5B-user-test-checklist.md`