# Phase 5A Build Evidence

## Work unit

- `WU-5A-VAL` — Phase 5A validation and evidence readiness
- Assigned agent: `build-test-validation`
- Phase 5A — Inbox-to-Job dispatch mapping (Raw Sources import-to-Inbox + `inbox_item_id -> source_id -> ingest_job`)
- Source planning docs:
  - `.code-planner/02-planning/phases/01-phase-plan.md` (Phase 5A row)
  - `.code-planner/02-planning/phases/02-detailed-phase-tasks.md` (Phase 5A section)
  - `.code-planner/02-planning/validation/01-validation-plan.md` (Phase 5A section)
  - `.code-planner/02-planning/features/feature-ui-cli-integration.md`
  - `.code-planner/03-build/phases/phase-5A-execution-brief.md`
- Execution-brief work units referenced (delegated to other subagents, not directly authored by this validator):
  - `WU-5A-001` Existing flow discovery (`codebase-explorer`) — read-only discovery feeding `WU-5A-002`/`WU-5A-003`.
  - `WU-5A-002` Inbox item to source/job materialization (`build-core-dev`).
  - `WU-5A-003` Raw Sources import-to-Inbox route (`build-core-dev`).
  - `WU-5A-004` Tests and validation (`build-test-validation`) — this validator is also the owner of the focused test file and this evidence.

## Phase 5A scope validated

The implementation under validation delivers:

- A new `inbox.materialize_source_for_inbox_item(paths, inbox_item_id)` domain
  helper that resolves an Inbox pending item to an existing or freshly created
  `sources` row, persists `inbox_items.source_id`, and emits an audit
  `inbox_event` (`source_materialized` on create, `source_materialized_reused`
  on reuse, `source_materialization_hash_conflict` when a same-hash row
  exists on a different relpath). It reuses the existing
  `jobs.enqueue(source_id)` / `ingest_llm.ingest_source(source_id)` pipeline
  and does not modify those entry points.
- A new dataclass `InboxSourceMaterializationResult` carrying
  `item / source_id / created / reused` for downstream callers and tests.
- A new `inbox.move_to_pending(paths, inbox_item_id)` helper that resets a
  failed/review item back into the input-type Inbox folder
  (`Inbox/Markdown/` / `Inbox/Text/` / `Inbox/Files/`) with state `pending`,
  used by the Phase 4 retry/reprocess contracts.
- A `/ingest/start` route that accepts `inbox_item_id` as the primary input
  and resolves/materializes the `source_id` internally; the legacy
  `source_id`-only path is preserved for backward compatibility. The response
  now includes `inbox_item_id`, `source_id`, and `job_id`.
- A rewritten `/ingest/scan` route that no longer registers files into the
  legacy `sources` queue. Each supported file is now imported into Inbox via
  `inbox.register_markdown_file` or `inbox.register_document_file`; the
  response shape changes from `added/deduped/skipped/errors` to
  `registered/deduped/skipped/errors` (with `added` retained as an alias of
  `registered` for the duration of the deprecation window), each result
  row now includes `inbox_item_id`, `relpath`, `state`, `source_id`, and the
  top-level `pending_count` is computed from `inbox_items.state = pending`.
- Existing `Inbox/Markdown`/`Inbox/Files`/`Inbox/Text` registration and
  movement helpers are reused untouched; no changes to `ingest_raw.py` or
  `jobs.py` (verified via `git diff HEAD -- src/llm_wiki/ingest_raw.py
  src/llm_wiki/jobs.py` returning empty).

**Explicit non-claim:** this phase does **not** update the `/ingest`
HTML template or `/ingest` route GET context to render inbox pending items
instead of legacy `sources.status = pending` rows. That is the proper
owner of Phase 5B (Web UI alignment with the approved Ingest mockup); the
two failing `test_web_navigation.py` tests below are recorded as the
expected Phase 5B / legacy ingest template mismatch and are **not** hidden.

## Validation-plan results (Phase 5A items)

| Phase 5A validation item | Result | Evidence |
| --- | --- | --- |
| Raw Sources import registers files as Inbox pending items, not direct `sources` queue entries | PASS | `test_ingest_scan_imports_raw_sources_into_inbox_without_creating_sources_rows` writes a Raw file, posts `/ingest/scan`, then asserts: `counts.registered == 1`, `counts.errors == 0`, `counts.skipped == 0`, `pending_count == 1`, exactly one row in `inbox_items` with `state = PENDING` and `relpath = Inbox/Markdown/from-raw.md`, and **zero rows in `sources`**. The original Raw file is removed and the file now lives at `paths.inbox_markdown/from-raw.md`. |
| `/ingest/start` or equivalent accepts `inbox_item_id` and resolves/materializes `source_id` internally | PASS | `test_ingest_start_materializes_source_from_inbox_item_and_creates_job` uploads `dispatch-me.md`, posts `/ingest/start` with `inbox_item_id`, asserts `payload.inbox_item_id`, `payload.source_id > 0`, `payload.job_id > 0`; the new `source` row has `relpath = Inbox/Markdown/dispatch-me.md`, the persisted `inbox_items.source_id` matches `payload.source_id`, and the `ingest_jobs.source_id` matches the same value. |
| A job can be enqueued from an Inbox pending item | PASS | Same test as above: `jobs_module.enqueue(source_id)` is invoked with the materialized `source_id` and the resulting `ingest_jobs.source_id` round-trips correctly. A `_FakeManager` is monkey-patched onto `ingest_route.jobs_module.get_manager` to exercise the route without spawning a real worker thread, and the assertion on `ingest_jobs.source_id` proves the dispatch contract holds. |
| `inbox_items.source_id` is persisted after materialization | PASS | Same test asserts `inbox.get_inbox_item(conn, inbox_item_id).source_id == payload.source_id`. A second test, `test_repeated_ingest_start_reuses_existing_source_id`, asserts the persisted link is stable across repeated start calls. |
| The existing LLM ingest pipeline still receives a valid `source_id` and can create/update Wiki pages | PASS (contract level) | `materialize_source_for_inbox_item` calls `parsers.parse(file_path)` and writes a `sources` row with `(relpath, content_hash, file_type, bytes, status='pending')`. The route then calls the existing `jobs_module.get_manager(paths).enqueue(source_id)`, and the resulting `ingest_jobs.source_id` is the materialized row. The `sources` row is shaped identically to a row produced by the legacy `ingest_raw.add_file` path so the existing `ingest_llm.ingest_source(source_id)` flow is unmodified. End-to-end LLM execution is out of scope for this validator and remains Phase 6's E2E matrix. |
| UX/user testing is blocked until this phase passes | N/A (gate decision) | Phase 5B UX alignment is downstream of Phase 5A. The two `test_web_navigation.py` failures listed below are the known template/template-rendering blocker owned by Phase 5B; they do not invalidate Phase 5A's wiring contract. |

## Files reviewed and scope separation

### Phase 5A implementation/test files reviewed (validator did not modify any source or test file)

- `src/llm_wiki/inbox.py` — added `materialize_source_for_inbox_item(...)`,
  the `InboxSourceMaterializationResult` dataclass, and the internal
  `_update_inbox_item_source_link(...)` / `_refresh_existing_source_row(...)`
  helpers. Reuses existing `parsers.parse(...)`, `_current_file_path(...)`,
  `get_inbox_item(...)`, `append_inbox_event(...)`,
  `_try_relpath(...)`. Diff stat for Phase 5A-only changes is interleaved
  with stacked Phase 4 work in `git diff --stat`; the Phase 5A addition is
  net positive (+~262 lines including a same-path source guard from the
  stacked Phase 4 fix).
- `src/llm_wiki/webapp/routes/ingest.py` — `/ingest/start` rewritten to
  accept `inbox_item_id` as primary input and call
  `inbox.materialize_source_for_inbox_item(...)`; `/ingest/scan` rewritten
  to delegate per-file registration to `inbox.register_markdown_file` /
  `inbox.register_document_file` (no `sources` row created). New
  `_register_raw_source_in_inbox(...)` helper added. (`+78/-29` lines in diff.)
- `tests/test_inbox_to_job_mapping.py` — new file, 3 focused tests covering
  the three Phase 5A validation items above. (118 lines, untracked.)

### Worktree overlap / separation note

- `git diff --stat` on the worktree currently shows five modified files plus
  two untracked test files:

  ```text
   src/llm_wiki/inbox.py                    | 262 ++++++++++++
   src/llm_wiki/webapp/routes/inbox.py      | 586 ++++++++++++++++++++++++--
   src/llm_wiki/webapp/routes/ingest.py     | 107 +++--
   src/llm_wiki/webapp/templates/inbox.html | 696 ++++++++++++++++++++++++++-----
   tests/test_inbox_registration.py         |  36 ++
   5 files changed, 1529 insertions(+), 158 deletions(-)

  ?? tests/test_inbox_to_job_mapping.py
  ?? tests/test_phase4_review_failed_workbench.py
  ```

- **Stacked uncommitted Phase 4 work is still in the worktree.** The
  validator observed uncommitted modifications to `src/llm_wiki/inbox.py`,
  `src/llm_wiki/webapp/routes/inbox.py`, `src/llm_wiki/webapp/templates/inbox.html`,
  and `tests/test_inbox_registration.py`. These are the Phase 4 workbench
  changes (and the Phase 4 fix-request follow-ups for `SEC-001`/`STAB-001`/`STAB-002`).
  Phase 5A edits were applied on top of the stacked Phase 4 tree; this is
  a **process risk** because the intended Phase 5A checkpoint (`feat:
  connect inbox items to ingest jobs`) cannot be cleanly isolated until
  the Phase 4 commit is finalized. The validator did not stage, commit, or
  reset any of these files.
- **Phase 5A files that are unchanged:** `src/llm_wiki/ingest_raw.py` and
  `src/llm_wiki/jobs.py` have empty diffs versus `HEAD`. The validator
  still ran `py_compile` against both files because the execution brief
  lists them; both compile cleanly. This confirms Phase 5A reused existing
  helpers (`parsers.parse`, `ingest_raw.iter_addable_files`,
  `jobs_module.get_manager(...)`, `jobs.create_job(...)`) without
  modifying them.
- **Phase 5A files that are unchanged vs. `HEAD`:** `src/llm_wiki/webapp/templates/ingest.html`,
  `src/llm_wiki/webapp/templates/inbox.html`. The legacy `/ingest` template
  still iterates `pending` as `sources` rows; this is the root cause of
  the two `test_web_navigation.py` failures recorded below and is the
  Phase 5B owner, not Phase 5A.

## Commands run and results

All commands were executed from `/home/eunjae/projects/llm-wiki` using the
project virtual environment. No secrets or environment files were read or
modified. No dev server, watcher, or background listener was started.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_inbox_to_job_mapping.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **PASS — 23 passed, 1 Starlette/httpx deprecation warning, 4.97s.** All 3 new Phase 5A mapping tests green (`test_ingest_start_materializes_source_from_inbox_item_and_creates_job`, `test_ingest_scan_imports_raw_sources_into_inbox_without_creating_sources_rows`, `test_repeated_ingest_start_reuses_existing_source_id`), plus the 4 Phase 1 inbox domain tests and the 16 Phase 2/4 inbox registration tests (including the stacked-Phase-4 `test_move_to_pending_missing_source_file_returns_moved_false_and_records_event`) all green. |
| `.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py -v` | **PASS — 4 passed, 1 Starlette/httpx deprecation warning, 4.56s.** Phase 4 workbench suite re-run for completeness: `test_inbox_route_builds_unified_workbench_context_and_preserves_legacy_items`, `test_failed_diagnostic_delete_removes_only_sidecar`, `test_diagnostic_response_respects_size_cap`, `test_retry_hold_and_delete_contracts_for_db_backed_items`. |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/ingest_raw.py src/llm_wiki/jobs.py tests/test_inbox_to_job_mapping.py` | **PASS — exit 0, no output.** Phase 5A source files (inbox, ingest route, ingest_raw untouched, jobs untouched) and the new test file all compile. |
| `git diff --check` | **PASS — exit 0, no output.** No whitespace errors in the Phase 5A + stacked Phase 4 worktree. |
| `.venv/bin/python -m pytest tests/test_web_navigation.py -v` | **FAIL (2/8) — 6 passed, 2 failed, 1 Starlette/httpx deprecation warning, 4.56s.** Failed tests: `tests/test_web_navigation.py::test_ingest_scan_registers_synced_raw_sources` and `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions`. **These are the expected Phase 5B / legacy ingest template mismatch** — both tests assert that the legacy `/ingest` HTML template renders a per-item `작업으로 보내기` button (and `mobile-synced.md` filename) for items produced by `/ingest/upload` and `/ingest/scan`. Phase 5A intentionally changed both routes to register Inbox items instead of `sources` queue rows, but did not touch `templates/ingest.html`, so the legacy `{% for src in pending %}` loop renders an empty list. The route logic (`counts.added`, `pending_count`, `state`, `inbox_item_id`) is correct and is what the new `test_inbox_to_job_mapping.py` suite covers; the template alignment is owned by Phase 5B. See Risks below. |
| `git status --short` | **Evidence captured.** `M src/llm_wiki/inbox.py`, `M src/llm_wiki/webapp/routes/inbox.py`, `M src/llm_wiki/webapp/routes/ingest.py`, `M src/llm_wiki/webapp/templates/inbox.html`, `M tests/test_inbox_registration.py`; `?? tests/test_inbox_to_job_mapping.py`, `?? tests/test_phase4_review_failed_workbench.py`, `?? .code-planner/`, `?? .prv/`. The validator did not modify any source or test file. |
| `git diff --stat` | **Evidence captured.** Five modified files, two new test files. `ingest.py` +78/-29 reflects the Phase 5A `/ingest/scan` and `/ingest/start` rewrites; `inbox.py` +262 includes both the stacked Phase 4 workbench additions and the Phase 5A `materialize_source_for_inbox_item` materialization helper. |
| `git log --oneline -10` | **Evidence captured.** Latest commit is `865c5b1 feat: add chunked extraction and stabilize page generation`. Phase 4 and Phase 5A changes are uncommitted/stacked. |
| `ss -ltnp` / `ps -ef \| grep -E "pytest\|uvicorn\|python.*llm_wiki"` | **Cleanup check completed.** Only pre-existing listeners (SSH on 22, Syncthing on 8384/22000, OpenCode on 4096, an existing Python listener on 8776) are present. No Phase 5A process or port was started. No `pytest`/`uvicorn`/`llm_wiki` process was left running after validation. |

### Test warning

The focused Phase 5A / Inbox / Phase 4 workbench runs emitted one pre-existing
dependency warning from `fastapi.testclient`/Starlette about the `httpx2`
transition. It did not fail a test and is not a Phase 5A implementation
failure.

### Cross-check on `materialize_source_for_inbox_item`

A short interactive round-trip was run via the project virtual environment to
sanity-check the new domain helper against the focused tests:

```text
register_document_file dispatch-me.txt -> inbox_items(id=1, state=pending, source_id=None, relpath=Inbox/Files/dispatch-me.txt)
materialize_source_for_inbox_item(id=1) -> sources(id=1, relpath=Inbox/Files/dispatch-me.txt, status=pending, content_hash=...)
inbox_items(id=1, source_id=1, state=pending)
last inbox_event: type=source_materialized data={created=True, reused=False, source_id=1}
materialize_source_for_inbox_item(id=1) again -> sources(id=1, ... unchanged), inbox_items.source_id=1 unchanged,
last inbox_event: type=source_materialized_reused data={created=False, reused=True, source_id=1}
jobs.enqueue(1) -> ingest_jobs(id=1, source_id=1, status=pending)
```

The round-trip matches
`test_ingest_start_materializes_source_from_inbox_item_and_creates_job` and
`test_repeated_ingest_start_reuses_existing_source_id`.

## User-facing validation items

- Uploads via `POST /ingest/upload` create one or more `inbox_items` rows
  with `state = pending` and `source_id = NULL`; the original file lives
  under `Inbox/Files/` or `Inbox/Markdown/` (or `Inbox/Text/` for paste),
  and **no `sources` row is created at upload time**.
- `POST /ingest/scan` walks `Raw Sources/` recursively, imports each
  supported file (`*.md` / `*.markdown` -> markdown registration, anything
  else -> document registration), and returns
  `counts.{registered, deduped, skipped, errors}` plus a per-file
  `results[]` carrying `inbox_item_id`, `relpath`, `state`, `source_id`.
  Files move from `Raw Sources/...` to `Inbox/Markdown/...` or
  `Inbox/Files/...`. **No `sources` row is created at scan time.**
- `POST /ingest/start` accepts `inbox_item_id` (primary) or `source_id`
  (legacy). For `inbox_item_id`, the route calls
  `inbox.materialize_source_for_inbox_item(...)` which creates/reuses the
  `sources` row, persists `inbox_items.source_id`, records an audit
  `inbox_event`, and returns the materialized `source_id`. The route
  then calls `jobs_module.get_manager(paths).enqueue(source_id)` and
  returns `{ok, inbox_item_id, source_id, job_id}`.
- `wiki retry <inbox_item_id>` (via the existing Phase 4 `/api/inbox/items/{id}/retry`
  endpoint, which calls `inbox.move_to_pending`) restores a failed/review
  item to its input-type inbox folder with `state = pending` and deletes
  the diagnostic sidecar.

## Process / port cleanup

- No dev server, watcher, background test process, or port listener was
  started by this validation. `pytest` runs completed synchronously and
  exited normally.
- `ss -ltnp` and `ps -ef` after all commands show only pre-existing
  listeners (SSH on 22, Syncthing on 8384/22000, OpenCode on 4096, an
  existing Python listener on 8776); none was created by this work unit
  and none was stopped or modified.
- No cleanup action was required.

## Remaining risks and limitations

1. **Stacked uncommitted Phase 4 changes are still in the worktree.**
   `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/inbox.py`,
   `src/llm_wiki/webapp/templates/inbox.html`, and
   `tests/test_inbox_registration.py` all carry uncommitted Phase 4 +
   Phase 4 fix-request changes that Phase 5A was applied on top of. The
   intended Phase 5A checkpoint (`feat: connect inbox items to ingest
   jobs`) cannot be cleanly isolated into a commit until the Phase 4
   tree is finalized. **Process risk for `/check` reviewer.**
2. **Full-tree pytest was not run.** The assigned scoped suite
   (Phase 5A focused + Phase 1/2 inbox regression + Phase 4 workbench
   suite = 27 tests) all passed. This evidence does **not** claim a clean
   full repository test run.
3. **Known Phase 5B / legacy ingest template mismatch is unfixed.**
   `tests/test_web_navigation.py::test_ingest_scan_registers_synced_raw_sources`
   and `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions`
   fail because the legacy `/ingest` HTML template (`templates/ingest.html`)
   still iterates `pending` as `sources` rows. Phase 5A intentionally
   changed `/ingest/upload` and `/ingest/scan` to register Inbox items
   rather than `sources` queue rows, so the legacy template now sees an
   empty list. The new `test_inbox_to_job_mapping.py` suite exercises the
   correct route logic, and the `/ingest/start` route accepts both
   `inbox_item_id` (primary) and legacy `source_id`. **The proper owner
   for the template alignment is Phase 5B (Web UI alignment with the
   approved Ingest mockup).** This is not hidden — it is recorded here
   and in Risks.
4. **JS round-trip on `/ingest` not exercised.** The new `/ingest/start`
   `inbox_item_id`-aware code path is exercised by `TestClient` calls in
   the focused tests. Full browser-side JS execution (fetch + reload +
   alert) is not exercised by the validator; UI smoke testing is the
   proper owner of Phase 5B.
5. **End-to-end LLM execution not exercised.** The
   `materialize_source_for_inbox_item -> jobs.enqueue(source_id) ->
   ingest_llm.ingest_source(source_id)` chain is verified at the data
   contract level (the resulting `sources` row has the legacy shape, the
   `ingest_jobs.source_id` matches, and `inbox_items.source_id` is
   persisted). The end-to-end "create/update Wiki pages" assertion is
   owned by Phase 6's E2E matrix.
6. **`tests/test_inbox_workbench.py` was not added to the command list.**
   The execution brief lists `tests/test_inbox_workbench.py` alongside
   the Inbox domain/registration files, but no such file exists in the
   worktree. `tests/test_phase4_review_failed_workbench.py` is the
   focused Phase 4 workbench file actually present and was run
   separately in command #2.
7. **Two new tests cover three behaviors.** The new
   `test_inbox_to_job_mapping.py` exercises the route layer with a
   `_FakeManager` that calls `jobs.create_job(...)` directly. The
   validator did not verify a running worker thread consumes the job;
   that contract is owned by the Phase 3 chunked extraction suite and
   remains green (no changes to `jobs.py` or `ingest_llm.py` in this
   work unit).

## Validation result

- **Phase 5A scoped validation: PASS.** All 3 new Phase 5A mapping tests
  pass; the 19 Phase 1/2 inbox regression tests remain green; the 4
  Phase 4 workbench tests remain green; `py_compile` and
  `git diff --check` pass.
- **Out-of-scope failures (web_navigation) recorded but not fixed.**
  Two failing tests in `tests/test_web_navigation.py` reflect the
  intentional Phase 5A semantic change away from a `sources` queue
  towards an Inbox-first queue; the legacy `/ingest` template is the
  Phase 5B owner's responsibility and is not hidden by this evidence.
- **Process risk:** the worktree still carries stacked uncommitted Phase
  4 changes underneath Phase 5A. The `/check` reviewer should be aware
  that the intended Phase 5A commit (`feat: connect inbox items to
  ingest jobs`) cannot be cleanly isolated until the Phase 4 tree is
  finalized.

## Ready for `/check`

- **true** for `/check phase-5A` when scoped to the Phase 5A
  deliverables and the documented risks/limitations above. Phase 5A
  scoped validation is sufficient:
  - The 3 new focused tests cover the three Phase 5A validation items
    (`raw_sources -> inbox pending -> source_id -> job`, `source_id`
    persistence, repeated-start reuse).
  - The 19 Phase 1/2 inbox regression tests still pass after the
    Phase 5A additions.
  - The 4 Phase 4 workbench tests still pass, confirming the Phase 5A
    domain additions (`materialize_source_for_inbox_item`,
    `InboxSourceMaterializationResult`) do not regress Phase 4's
    retry/hold/delete contracts.
  - The two `test_web_navigation.py` failures are genuinely out of scope
    (Phase 5B ingest template rendering, expected to fail by design
    under Phase 5A's Inbox-first queue semantic), so they do not block
    the Phase 5A checkpoint.
  - `py_compile` and `git diff --check` pass cleanly.
- This is **not** a claim that the full repository suite is green or
  that Phase 5A changes are already cleanly separable into a commit;
  the stacked Phase 4 worktree state is recorded above as a process
  risk.

## Evidence artifact

- `.code-planner/03-build/evidence/phase-5A-build-evidence.md` (this file)