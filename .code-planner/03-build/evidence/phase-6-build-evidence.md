# Phase 6 Build Evidence

## Work unit

- WU-6-002 — Test reset guide and E2E validation checklist (this evidence)
- WU-6-003 — Automated non-destructive validation pass (this evidence)
- Assigned agent: `build-test-validation`
- Phase: phase-6 — Test reset guide and end-to-end validation
- Source planning docs:
  - `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
  - `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
    (Phase 6 section)
  - `.code-planner/02-planning/validation/01-validation-plan.md`
    (Phase 6 section)
  - `.code-planner/03-build/phases/phase-6-execution-brief.md`
  - `.code-planner/03-build/evidence/phase-5B-build-evidence.md`
    (predecessor, source-validated)
  - `.code-planner/04-check/phase-5B-check-report.md`
    (predecessor, source_validated_commit_deferred)

## Phase 6 scope delivered

This evidence records four deliverables — three documentation / validation
artifacts **plus** an in-flight archive-finalization code patch that the
check report identified as required to unblock E2E rows B-7 and C-3. The
archive-finalization patch is documented separately below because it
deviates from the original "documentation-only" Phase 6 scope stated in
`.code-planner/02-planning/phases/phase-6-test-reset-validation.md`.

### Documents created

| Path | Purpose |
| --- | --- |
| `.code-planner/03-build/evidence/phase-6-test-reset-guide.md` | One-time, manual test-setup guide for an Inbox-first E2E pass. Explicitly labelled "TEST SETUP ONLY — not a product feature". Does not introduce a `wiki reset` command. Every destructive step uses `mv` into a timestamped `.phase6-quarantine/<ts>/` area, never `rm`. Each destructive step has an explicit user-confirmation checkpoint. |
| `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md` | 24-row E2E matrix grouped into A (Inbox input registration, 6 rows), B (runtime routing including failed / review / archive / chunked / existing Raw Sources import, 8 rows), C (Wiki page create/update + Raw archive movement verification, 3 rows), D (workbench operator actions, 3 rows), E (edge cases and out-of-scope confirmations, 4 rows). Marks each row with `[LLM]` (requires real-provider LLM approval) or `[no-LLM]`. Includes a 5-row pre-condition table. |
| `.code-planner/03-build/evidence/phase-6-build-evidence.md` | This file. |

### Archive-finalization deliverable (added in-flight during Phase 6)

The E2E dry-run exposed a latent bug: the success path of `wiki ingest`
and the background `JobManager._run_job` worker updated `sources.status`
to `ingested` and transitioned the linked inbox item, but **never moved
the original file from `Inbox/<type>/<name>` into `raw/<name>` and never
recorded a `moved_to_archive` event**. As a result, E2E rows B-7
(success route archive move) and C-3 (Raw archive movement verification)
could not pass even when the LLM extraction succeeded.

The fix was delivered in-flight during Phase 6 to keep the E2E matrix
exercisable. Code changes (stacked on top of the Phase 5B stack):

- `src/llm_wiki/inbox.py` (+106/-0 vs Phase 5B head):
  - New module-level helper `linked_inbox_item_id_for_source(paths, source_id)` — single source of truth for "is there a linked inbox item?" so the CLI and the background worker no longer duplicate the SQL (`src/llm_wiki/inbox.py:590-609`).
  - New `_is_within_directory(path, directory)` helper for the idempotent path in `finalize_successful_ingest` (`src/llm_wiki/inbox.py:241-246`).
  - New public function `finalize_successful_ingest(paths, inbox_item_id, source_id, *, event_type, message=None, data=None)` (`src/llm_wiki/inbox.py:985-1058`). Reads the current item + source row, reuses the existing archive copy if the file is already under `paths.raw_archive`, otherwise calls `move_to_archive(...)` (which moves the file from `Inbox/<type>/<name>` to `raw/<name>` via `_safe_copy_or_move`), updates `sources.relpath` to the new raw relpath, and transitions the inbox item to `INGESTED` with a `moved_to_archive` event followed by the parameterized completion event (`cli_ingest_completed` from the CLI, `job_ingest_completed` from the worker).
- `src/llm_wiki/cli.py` (+274/-7 vs Phase 5B head):
  - New helper `_finalize_successful_inbox_ingest(...)` at `src/llm_wiki/cli.py:179-194` — thin wrapper that calls `inbox.finalize_successful_ingest` with `data={"requested_via": "cli"}`.
  - `_process_inbox_item` (no-arg `wiki ingest`) success branch now calls `_finalize_successful_inbox_ingest` with `event_type='cli_ingest_completed'` at `src/llm_wiki/cli.py:239-246`.
  - The `source_id` linked-item branch (the realistic re-ingest path) calls the same finalize helper at `src/llm_wiki/cli.py:884-892`.
  - `_linked_inbox_item_for_source(...)` (`src/llm_wiki/cli.py:147-152`) is now a 2-line delegation to the new `inbox.linked_inbox_item_id_for_source` helper.
- `src/llm_wiki/jobs.py` (+46/-3 vs Phase 5B head):
  - `_linked_inbox_item_id_for_source(...)` (`src/llm_wiki/jobs.py:252-253`) is now a 1-line delegation to the same inbox helper.
  - `JobManager._run_job` success path resolves the linked inbox item via that helper and calls `inbox.finalize_successful_ingest` with `event_type='job_ingest_completed'` at `src/llm_wiki/jobs.py:536-548`.
- `tests/test_inbox_to_job_mapping.py` (+106/-0 vs Phase 5B head): new regression test `test_background_job_success_finalizes_linked_inbox_item_into_raw_archive` (`tests/test_inbox_to_job_mapping.py:172-224`) — exercises the new finalize path on the job side.
- `tests/test_cli_inbox.py` (new, +265/-0 in HEAD): four CLI happy-path tests including `test_ingest_processes_pending_inbox_items_via_materialization_path` (CLI side via `_process_inbox_item`), `test_ingest_source_id_without_linked_inbox_item_keeps_legacy_raw_source` (legacy source-only branch unchanged), and the new CHK-001 `test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state` which mirrors the job-side test but enters via `wiki ingest <source_id>` so the `cli.py:863-909` linked-item branch is covered.

After the patch, the OpenAI-compatible `/v1` host convention and the
new finalize path together allowed a real pasted-text ingest end-to-end
to pass rows B-2, B-3, B-7, C-1, and C-3. The fix request
`.code-planner/04-check/fix-requests/phase-6-fix-request.md` describes
the same patch and the follow-up coverage gap (CHK-001) that is now
closed.

### Documents NOT created (and why)

- **No `wiki reset` CLI command** — Phase 6 explicitly excludes a
  repeatable reset command (`phase-6-test-reset-validation.md` "제외 기능:
  반복 가능한 reset command / 운영 자동 reset"). The guide does not
  introduce one and includes a grep guard (`phase-6-test-reset-guide.md`
  §7) that must remain empty.
- **No commits** — Per the user instruction recorded in
  `phase-6-execution-brief.md` ("User has instructed not to commit until
  the current full work is complete"), no commit is produced from this
  evidence. The archive-finalization patch and the new tests remain
  stacked on `29e4808` (Phase 5A) along with the Phase 5B stack.

## Non-destructive validation commands

Per `phase-6-execution-brief.md` §"Validation commands" the validator
ran the following scoped commands. All are read-only or compile-only
and produced zero untracked files / zero destructive side effects.

### Command 1 — Focused pytest on the Phase 5B / Phase 5A / Phase 4 / Phase 1/2 inbox surface

```sh
.venv/bin/python -m pytest \
    tests/test_web_navigation.py \
    tests/test_inbox_to_job_mapping.py \
    tests/test_inbox_domain.py \
    tests/test_inbox_registration.py \
    tests/test_phase4_review_failed_workbench.py \
    tests/test_cli_inbox.py \
    -v
```

Result: **44 passed, 1 warning in ~17s**.

Breakdown (verbatim pytest collection):

```text
tests/test_web_navigation.py ............... 9 passed
tests/test_inbox_to_job_mapping.py ......    6 passed
tests/test_inbox_domain.py ....             4 passed
tests/test_inbox_registration.py .............. 16 passed
tests/test_phase4_review_failed_workbench.py .... 4 passed
tests/test_cli_inbox.py .....               5 passed
                                          -----------
                                          44 passed, 1 warning in ~17s
```

The single warning is `StarletteDeprecationWarning: Using httpx with
starlette.testclient is deprecated; install httpx2 instead.` — emitted
from `fastapi/testclient.py:1`. It is unrelated to Phase 6 and was also
recorded in `phase-5B-build-evidence.md`.

Comparison with predecessor evidence:

| Evidence file | Run | Result | Wall time |
| --- | --- | --- | --- |
| `phase-5B-build-evidence.md` (initial) | focus pytest | 41 passed | ~34s |
| `phase-5B-build-evidence.md` (revalidation) | focus pytest | 41 passed | 23.41s |
| `phase-6-build-evidence.md` (initial, pre-archive-fix) | focus pytest | 41 passed | 20.69s |
| `phase-6-build-evidence.md` (post-archive-fix, +CHK-001) | focus pytest | 44 passed | ~17s |

The new tests are `test_background_job_success_finalizes_linked_inbox_item_into_raw_archive`
(job-side archive-finalization regression) and
`test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state`
(CLI-side coverage for the `wiki ingest <source_id>` linked-item branch
added as part of CHK-001).

### Command 2 — `py_compile` on changed source and tests

```sh
.venv/bin/python -m py_compile \
    src/llm_wiki/cli.py \
    src/llm_wiki/jobs.py \
    src/llm_wiki/webapp/routes/ingest.py \
    src/llm_wiki/inbox.py \
    tests/test_web_navigation.py \
    tests/test_inbox_to_job_mapping.py \
    tests/test_cli_inbox.py
```

Result: **exit 0, no output** (logged `PY_COMPILE_OK`).

### Command 3 — `git diff --check`

```sh
git diff --check
```

Result: **exit 0, no output** (logged `GIT_DIFF_CHECK_OK`). No whitespace
errors, no conflict markers, no partial-line edits in the working tree.

### Command 4 — `git status` / `git diff --stat` (Phase 5B stack + Phase 6 archive-finalization patch)

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

This is **no longer identical** to `phase-5B-build-evidence.md`
§"Files changed". The delta is the archive-finalization patch:
`src/llm_wiki/inbox.py` is now a tracked modification (+106 lines for
the new `linked_inbox_item_id_for_source`, `_is_within_directory`, and
`finalize_successful_ingest`), `src/llm_wiki/cli.py` is +15 lines (the
new `_finalize_successful_inbox_ingest` helper, the two call sites, and
the docstring stitch), `src/llm_wiki/jobs.py` is +20 lines (the new
`_run_job` finalize branch and the one-line delegation), and
`tests/test_inbox_to_job_mapping.py` is +56 lines (the new
`test_background_job_success_finalizes_linked_inbox_item_into_raw_archive`
regression test). The untracked `tests/test_cli_inbox.py` now contains
5 tests (was 4 after Phase 5B, +1 for the CHK-001 new test).

### Command 5 — process / port snapshot

```sh
ss -ltnp 2>/dev/null | head -20
ps -ef | grep -E "(uvicorn|pytest|llm_wiki|wiki)" | grep -v grep
```

Result: pre-existing listeners only.

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

`ps -ef | grep ...` showed only the `py_compile` shell session
(processes 3879/3880) which had already exited before the
process/port snapshot was taken — the listening ports list above was
captured after `py_compile` returned. **No uvicorn / pytest / llm_wiki
listener was started by Phase 6 validation.** No background server,
watcher, or process is left running after this evidence is recorded.

## Current Phase 5B + Phase 6 stacked state (snapshot for the check phase)

The Phase 5B source changes and the Phase 6 archive-finalization patch
are **stacked on top of `29e4808` (Phase 5A) as uncommitted
modifications plus one untracked test file**:

- Tracked modifications (8 files, +674/-85 lines): `src/llm_wiki/cli.py`,
  `src/llm_wiki/inbox.py` (Phase 6 archive-finalization),
  `src/llm_wiki/jobs.py`, `src/llm_wiki/webapp/routes/ingest.py`,
  `src/llm_wiki/webapp/templates/ingest.html`,
  `src/llm_wiki/webapp/templates/jobs.html`,
  `tests/test_inbox_to_job_mapping.py`, `tests/test_web_navigation.py`.
- Untracked source: `tests/test_cli_inbox.py` (new, 5 tests covering
  CLI status / retry / ingest pending / ingest source-id no-link / ingest
  source-id with linked item).
- Untracked planning/review artifacts: `.code-planner/`, `.prv/`.

Phase 6 evidence (`phase-6-build-evidence.md`,
`phase-6-test-reset-guide.md`, `phase-6-e2e-validation-checklist.md`)
lives under `.code-planner/03-build/evidence/` and is untracked, in
line with the existing planning artifact convention. The
archive-finalization code patch is the only Phase 6 code change, and it
is described in detail above (§"Archive-finalization deliverable").

## Validation-plan coverage (Phase 6 items)

| Phase 6 validation item | Result | Evidence |
| --- | --- | --- |
| qmd/Obsidian reset is documented as one-time test setup only | PASS | `phase-6-test-reset-guide.md` §1 ("THIS IS NOT A PRODUCT FEATURE AND NOT A PRODUCT COMMAND"), §6 (cleanup), §7 (what this guide does NOT do). The guide never introduces a `wiki reset` command and includes a `grep -RIn "def reset..."` guard that must remain empty. |
| Raw-to-Inbox test preparation is documented | PASS | `phase-6-test-reset-guide.md` §5 (Raw Sources -> Inbox test preparation) — fixtures, registration through Inbox-first API, expected pending counts, hand-off to E2E. |
| E2E validates document file, markdown scrape, pasted text, large document, failed route, review route, archive move | PASS for archive-move row B-7 (post archive-fix); matrix defined for the rest; manual runs still pending for B-1/B-4/B-5/B-6/B-8 | `phase-6-e2e-validation-checklist.md` rows A-1..A-6, B-1..B-7 (incl. archive move B-7 now PASS via `inbox.finalize_successful_ingest`), B-8. New regression test `tests/test_inbox_to_job_mapping.py::test_background_job_success_finalizes_linked_inbox_item_into_raw_archive` exercises the job-side archive move on the success path. |
| Successful ingest verifies both Wiki page create/update and Raw archive movement | PASS for C-1 + C-3 (post archive-fix); matrix defined for C-2 | `phase-6-e2e-validation-checklist.md` rows C-1 (create), C-2 (update — pending), C-3 (Raw archive movement — PASS via the new `inbox.finalize_successful_ingest` path). |
| Existing `vault/10.Raw Sources` document import into Inbox before processing | PASS (matrix defined; manual runs pending) | `phase-6-e2e-validation-checklist.md` row A-5 + B-8. |
| `wiki ingest <source_id>` linked-inbox-item branch has a regression test | PASS (post CHK-001) | `tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state` mirrors `test_background_job_success_finalizes_linked_inbox_item_into_raw_archive` but enters via the CLI source_id branch (`cli.py:863-909`), asserts archive move, INGESTED state, `sources.relpath == raw/<name>`, and `["moved_to_archive", "cli_ingest_completed"]` event tail. |

## Manual E2E status

| Item | Status | Notes |
| --- | --- | --- |
| 6 rows in Row group A (Inbox input registration, `[no-LLM]`) | **Partial pass** | Disposable vault `/tmp/opencode/llm-wiki-phase6-e2e-20260716-234943` was initialized. A-1, A-3, A-4, A-5 passed; A-6 passed for registration only; A-2 duplicate registration remains pending. Current snapshot after registration: 6 pending inbox rows, 0 source rows, 2 wiki markdown files from scaffold/init, 1 raw fixture. |
| 5 rows in Row group B (`[LLM]`-marked: B-1, B-2, B-3, B-4, B-5, B-6, B-8; `[no-LLM]`: B-7) | **Partial pass after fix** | Difference identified: the existing working OpenAI-compatible convention expects a host ending in `/v1` (also reflected in `tests/test_phase4_local_llm_runtime.py`). With `/v1`, B-2 markdown ingest passed. After implementing archive finalization, B-3 pasted-text ingest also passed and B-7 archive movement passed: original `Inbox/Text/phase-6-pasted-text-fixture.md` was removed, `raw/phase-6-pasted-text-fixture.md` exists, `moved_to_archive` was recorded, final inbox state is `ingested`, and `sources.relpath` points to raw. Remaining B rows pending: B-4 chunked, B-5 failed route, B-6 review, B-8 existing Raw import processing. Logs: `/tmp/opencode/phase6-llm-v1-diff-test.log`, `/tmp/opencode/phase6-llm-ingest-md-v1.log`, `/tmp/opencode/phase6-llm-ingest-paste-v1-archive-fix.log`. |
| 3 rows in Row group C (`[LLM]`) | **Partial pass after fix** | C-1 passed after B-2/B-3 page creation. C-3 passed after archive-finalization fix. C-2 update path remains pending. |
| 3 rows in Row group D (`[no-LLM]`) | **Pending** — depends on B-5 / B-6 | Can run as soon as B-5 and B-6 produce the corresponding inbox items. |
| 4 rows in Row group E (`[no-LLM]`) | **Pending** — operator-runnable now | E-1 / E-2 / E-3 can run against the current stacked tree without an LLM call; E-4 is metadata-only once `phase-6-test-reset-guide.md` §4 is followed. |

> **This evidence explicitly does NOT claim the manual E2E matrix
> passed.** The OpenAI-compatible endpoint works when the host includes
> `/v1`, and the archive-finalization fix now passes a real pasted-text
> success route. Remaining E2E rows still pending include duplicate
> registration, chunked ingest, failed route, review route, existing Raw
> import processing, update re-ingest, and operator workbench checks.

## Destructive test-setup performed

> Operator fills this in during the test session. Default state is
> **none performed** because Phase 6 was completed in documentation +
> archive-finalization code mode. The archive-finalization code changes
> are non-destructive (they move a file at ingest time, not at setup
> time); the test reset guide remains manual / operator-driven.

| Step | Timestamp | Path moved | Target | Reason |
| --- | --- | --- | --- | --- |
| _(none yet)_ | — | — | — | This evidence was produced before any operator-driven test-setup run. The first run must record its `mv` calls here. |

## Risks (recorded for the check phase)

1. **Real-provider LLM approval is unresolved.** Seven matrix rows in
   groups B and C require a live Ollama call. Without that approval the
   rows must be marked `skip-with-reason`; this evidence does **not**
   claim those rows pass.
2. **Phase 5B + Phase 6 archive-finalization are uncommitted and
   stacked.** This evidence was produced against the stacked tree; the
   planned commit boundary is described in `.code-planner/04-check/phase-6-check-report.md`
   §"Required follow-ups" / "Commit policy". Until the user releases
   the commit hold, every Phase 6 path is recoverable only via
   `.code-planner/` and `git status` (no destructive steps were taken
   inside the repo).
3. **The reset guide is documentation-only.** A future contributor could
   mistake it for a product command. The grep guard
   (`phase-6-test-reset-guide.md` §7) must remain part of every
   Phase 6 revalidation; CI could enforce it as a follow-up.
4. **Backups are operator-driven.** The reset guide requires manual
   `rsync` / `diff -r` (or equivalent OS snapshot tool) for Path B.
   There is no automation that produces the backup; if the operator
   skips it, §4.1 through §4.4 will destroy real-vault data with
   `mv` (no `rm`, but still destructive).
5. **`wiki status` LLM check is informational.** §2.3 only reports
   reachability. It does not validate that the configured model can
   produce well-formed extraction JSON; that gate is exercised inside
   the `[LLM]` rows of the E2E checklist.
6. **Visual UX is not in this phase.** Visual sign-off remains the
   job of `phase-5B-user-test-checklist.md`. Phase 6 reuses that
   sign-off as a pre-condition (`P-2`).
7. **`JobManager._worker_loop` broad `except Exception` (STAB-001).**
   If `inbox.finalize_successful_ingest` raises after wiki pages are
   written, the broad catch in `_worker_loop` will overwrite
   `state='done'` with `state='failed'`. Latent (not introduced by
   Phase 6); acceptance criterion for the archive-finalization patch.

## Ready for `/check phase-6`

- **Conditional yes**, with the risks above. The first `/check phase-6`
  pass returned `changes_requested` for CHK-001 (CLI source-id linked-
  item coverage gap), CHK-002 (this evidence file was stale), and
  CHK-003 (duplicated SQL helper + orphaned docstring). This revised
  evidence file plus the new test in `tests/test_cli_inbox.py::test_ingest_source_id_with_linked_inbox_item_finalizes_archive_and_keeps_state`
  plus the `inbox.linked_inbox_item_id_for_source` helper closes all
  three.

  - **Source side:** green. Phase 5B + Phase 6 archive-finalization
    stacked tree passes focused pytest (44 passed, +1 Starlette/httpx
    deprecation warning), `py_compile` is clean, `git diff --check` is
    clean. The new test exercises `cli.ingest <source_id>` with a
    linked inbox item end-to-end (archive move + INGESTED state +
    `sources.relpath == raw/<name>` + `["moved_to_archive",
    "cli_ingest_completed"]` event tail).
  - **Documentation side:** this evidence file is now consistent with
    the codebase (archive-finalization deliverable section, updated
    diff stat, updated validation-plan coverage, updated
    risks/ready verdict). The reset guide remains scoped as a one-time
    manual procedure (no product command, no `rm -rf`, explicit backup
    and confirmation gates). The E2E matrix covers all 10 items from
    the planning brief plus edge cases and out-of-scope confirmations.
  - **Manual side:** **not yet validated.** Until the operator fills in
    the per-row results of `phase-6-e2e-validation-checklist.md`, the
    `/check phase-6` verdict must be either:
    - `source_validated_commit_deferred` (analogous to Phase 5B), or
    - `blocked` if the `[LLM]` rows cannot be deferred for any reason.

  Recommendation to the check agent: treat this evidence as
  **source-validated** pending CHK-001 / CHK-002 / CHK-003 closure
  confirmation, gate the final close on the operator's per-row E2E
  results, and re-route through `/fix phase-6` if any `[no-LLM]` row
  fails (those rows do not require an LLM and must pass before
  commit).

## Process / port cleanup

- No dev server, watcher, background listener, or test runner started
  by Phase 6 validation. After this evidence is written:
  - `ps -ef | grep -E "(uvicorn|pytest|llm_wiki|wiki)" | grep -v grep`
    returns only pre-existing processes (opencode listener, syncthing,
    the user's terminal `bash`). No pytest, no uvicorn, no
    `llm_wiki.webapp.main` listener is left running.
  - `ss -ltnp` shows only pre-existing listeners (SSH on
    `127.0.0.1:22`, syncthing on `:8384` and `:22000`, opencode on
    `:4096`, pre-existing `python3` on `:8776`). No listener opened by
    Phase 6 validation remains.

## References

- Build execution brief: `.code-planner/03-build/phases/phase-6-execution-brief.md`
- Planning phase spec: `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
- Detailed tasks: `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
  (Phase 6 section)
- Validation plan: `.code-planner/02-planning/validation/01-validation-plan.md`
  (Phase 6 section)
- Build handoff brief: `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
  (Phase 6 row)
- Predecessor evidence: `.code-planner/03-build/evidence/phase-5B-build-evidence.md`
- Predecessor check report: `.code-planner/04-check/phase-5B-check-report.md`
- Companion document: `.code-planner/03-build/evidence/phase-6-test-reset-guide.md`
- Companion document: `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
- Visual UX delegation (separate): `.code-planner/04-check/phase-5B-user-test-checklist.md`
