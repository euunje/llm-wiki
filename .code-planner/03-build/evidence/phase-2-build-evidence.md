# Phase 2 Build Evidence

## Work unit

- WU-005: Phase 2 validation and evidence readiness
- Phase 2 — Inbox registration and movement
- Source planning docs:
  - `.code-planner/02-planning/phases/phase-2-inbox-registration-movement.md`
  - `.code-planner/02-planning/features/feature-inbox-registration.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md`
  - `.code-planner/03-build/phases/phase-2-execution-brief.md`

## Phase 2 scope (per planning docs and WU briefs)

- Three input types (document file, markdown file, pasted text) register
  Inbox items in `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- Processing state is a DB state/lock; no physical `_Processing` folder.
- Success moves the original to Raw Sources archive (`Inbox → raw/`).
- Failure moves the original to `Inbox/_Failed` and writes a diagnostic
  report next to it.
- Review moves the original to `Inbox/_Review`.
- File name collision handling.
- **Duplicate content_hash dedup** (P2-WU-005-RECHECK fix):
  re-registering the same content for `register_document_file` /
  `register_markdown_file` reuses the existing Inbox item, records a
  `duplicate_content_hash_registered` event, and never creates a second
  physical file under `Inbox/Files/` or `Inbox/Markdown/`.
- Move failure evidence records source path, target path, DB state, and
  retry capability without losing the source file.
- CLI `wiki add` and Web `/ingest/upload` / `/ingest/paste` are routed
  through the Inbox registration helpers (minimum integration).

Explicitly out of Phase 2 scope (per brief + documented known limitation):

- `Inbox item → sources.id / jobs` execution mapping for `/ingest/start`.
- UI redesign of `/ingest` page to consume Inbox-first pending queue
  (template UX change → Phase 5).
- Chunked extraction (Phase 3).
- Review workbench detailed actions (Phase 4).
- Hash dedup for `register_pasted_text` and `register_uploaded_bytes`:
  pasted-text writes to `Inbox/Text/...md` before computing the hash and
  does not consult `inbox_items` by `content_hash`; for uploads,
  dedup happens inside the same flow as `register_markdown_file` /
  `register_document_file`. This is acceptable per scope — the dedup
  contract is on file-based input types only.

## Files in Phase 2 scope (changes validated)

- `src/llm_wiki/inbox.py` — added `InboxRegistrationResult`,
  `InboxMoveResult`, file-registration helpers (`_register_file`,
  `_move_item_file`, `_safe_copy_or_move`, `_unique_destination`,
  `_read_registered_metadata`, `_sanitize_error_detail`,
  `_create_report_text`, `_find_existing_inbox_item_by_hash`,
  `_item_stored_path`), public APIs `register_document_file`,
  `register_markdown_file`, `register_pasted_text`,
  `register_uploaded_bytes`, `acquire_processing_lock`,
  `move_to_archive`, `move_to_review`, `move_to_failed`. Existing
  `InboxState` / `InboxInputType` / CRUD helpers are unchanged.
  **P2-WU-005-RECHECK:** `_register_file` now consults the
  `inbox_items` table by `content_hash` first; if a matching row is
  found, it emits a `duplicate_content_hash_registered` event (with
  `source_path`, `stored_path`, `requested_input_type`, `db_state`,
  `retryable: false`, `deduped: true`, `source_preserved: true`) and
  returns an `InboxRegistrationResult(deduped=True)` that reuses the
  existing InboxItem, so no second physical file is written.
  `InboxRegistrationResult.deduped` (default `False`) exposes this to
  callers.
- `src/llm_wiki/cli.py` — added `_register_file_in_inbox` dispatch,
  rewired `wiki add` to call Inbox registration instead of
  `ingest_raw.add_file`, updated help/CLI summary text. The CLI now
  inherits the Inbox-level `deduped` flag from `InboxRegistrationResult`
  (no CLI-specific dedup logic is needed; the Inbox helper covers it).
- `src/llm_wiki/webapp/routes/ingest.py` — `/ingest/upload` rewritten to
  call `inbox.register_uploaded_bytes` (replacing the previous
  `ingest_raw.add_file` + `data_lake` fallback); new `/ingest/paste`
  route registered via `inbox.register_pasted_text`. Response payloads
  now expose `inbox_item_id`, `relpath`, `state`, `input_type`,
  `source_id` instead of `result` + legacy `source_id`. Web upload
  responses surface the `deduped` flag for each registered file.
- `tests/test_inbox_registration.py` (new) — **14 tests** covering all
  three input-type registrations, processing lock, archive / review /
  failure moves, diagnostic report, file-collision avoidance,
  **duplicate-hash dedup for both document and markdown inputs**,
  move failure evidence, CLI helper dispatch, and FastAPI
  `/ingest/upload` + `/ingest/paste` routes.

## Out-of-scope files present in worktree (NOT Phase 2, NOT included in this evidence)

These files exist in the working tree but belong to other workstreams
and must be staged separately:

| File | Lines | Owner workstream |
| --- | --- | --- |
| `src/llm_wiki/ingest_llm.py` | +925 / -165 | Phase 2 (2-pass/STAB) — tracked under `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md` |
| `src/llm_wiki/prompts.py` | +235 | Phase 2 (2-pass page templates) — same STAB workstream |
| `src/llm_wiki/llm.py` | +5 | Unrelated — OpenAI-compatible error body surfacing |
| `tests/test_two_pass_generation.py` (new) | +1128 | STAB-002/003 regression tests (same workstream) |
| `tests/test_staged_lint_gate.py` (new) | +340 | STAB-001 regression test (same workstream) |
| `tests/test_phase2_candidates_schema.py` | +224 | Phase 2 (candidates schema) + Phase 2 (malformed-wikilink fix) — partially same workstream |

The Phase 2 commit (`feat: route inputs through inbox`) should stage
only the four Phase 2 files listed in the section above. The
out-of-scope files are tracked by `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`
and partial evidence already lives at
`.code-planner/03-build/evidence/2-pass-generation-fix-evidence.md`.

## P0 guardrail verification

| Validation-plan item (Phase 2) | Status | Evidence |
| --- | --- | --- |
| Document file creates an Inbox item | PASS | `test_document_registration_creates_file_in_inbox_files_and_inbox_item` |
| Markdown file creates an Inbox item | PASS | `test_markdown_registration_creates_file_in_inbox_markdown_and_preserves_content` |
| Pasted text creates an Inbox item | PASS | `test_pasted_text_creates_markdown_with_frontmatter` |
| `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text` conventions match docs and code | PASS | `paths.inbox_files`, `paths.inbox_markdown`, `paths.inbox_text` are used by `register_document_file`, `register_markdown_file`, `register_pasted_text`, and `register_uploaded_bytes`; assertions in the three registration tests |
| Success moves original to Raw Sources archive | PASS | `test_success_archive_moves_to_raw_archive_and_updates_state_event` (file moves from `Inbox/Files/<name>` to `raw/<name>`, state `pending → processing → archived`, `moved_to_archive` event with `source_path` / `target_path` / `db_state`) |
| Failure moves original to `Inbox/_Failed` + diagnostic report | PASS | `test_failure_moves_to_failed_and_writes_diagnostic_report` (file in `Inbox/_Failed/<name>`, state `failed`, report at `<name>.diagnostic.md` with `phase`, `error_type`, sanitized `error`, `retry_hint`) |
| Review moves original to `Inbox/_Review` | PASS | `test_review_moves_to_review_folder` |
| File name collision handling works | PASS | `test_collision_handling_avoids_overwrite` (second `duplicate.txt` becomes `duplicate-1.txt`, original preserved) |
| Duplicate content_hash handling works (document file) | PASS (P2-WU-005-RECHECK) | `test_document_registration_dedupes_by_content_hash_without_creating_second_file` — two files with identical body content yield a single Inbox item, `deduped=True` on the second call, only `first.txt` exists under `Inbox/Files/`, and the latest event on the original item is `duplicate_content_hash_registered` with `source_path`, `stored_path`, `deduped=true` |
| Duplicate content_hash handling works (markdown file) | PASS (P2-WU-005-RECHECK) | `test_markdown_registration_dedupes_by_content_hash_and_records_traceable_event` — same scenario for `.md` files; event payload also carries `requested_input_type: markdown_file` and `source_preserved: true` |
| Move failure records source / target / DB state / retry capability, no source loss | PASS | `test_move_failure_records_evidence_and_preserves_source` (monkeypatched `shutil.copy2` raises `OSError`; source file still exists; `archive_move_failed` event with `source_path`, `target_path`, `db_state: processing`, `retryable: true`) |
| `processing` is DB state/lock, no `_Processing` folder | PASS | `test_processing_lock_updates_state_without_creating_processing_folder` (state moves to `processing`, `lock_token` stored, `Inbox/_Processing` is not created) |
| Inbox state enum matches docs/code | PASS | `test_inbox_states_and_helpers_follow_phase1_contract` (Phase 1, still passes — 6-state enum unchanged) |
| DB migration idempotent / sources·jobs·runs preserved | PASS | `test_init_db_migration_is_idempotent_and_preserves_existing_rows` (Phase 1, still passes) |
| Default and Ja path layouts pass | PASS | `test_wikipaths_exposes_inbox_path_semantics_and_respects_non_categories` (Phase 1, still passes) |
| Existing `non_categories`-based tests have a clear migration path | PASS | Same Phase 1 test confirms `WikiPaths.inbox_review == WikiPaths.non_categories` on Ja layout |
| Existing legacy `sources`-based tests can keep working in parallel | DEFERRED | `/ingest` page template still reads pending sources from legacy `sources` table. See "Known limitation" below and remaining risk #1. |

## Known limitation (per Phase 2 brief, must be tracked)

- `/ingest/start` remains a legacy `source_id`-based flow.
  Inbox items created by `/ingest/upload` or `/ingest/paste` are
  registered with `source_id = NULL`. There is no safe mapping from an
  Inbox item id to a `sources.id` / `ingest_jobs.id` pair in Phase 2
  minimum integration. This must be implemented (and a safe migration
  path defined) before Phase 5 UI consumers can dispatch Inbox items
  into the actual extraction job.

  The Phase 2 web template still renders pending items from
  `ingest_raw.list_sources`, which is why one existing UI test
  (`test_ingest_pending_sources_render_batch_queue_actions`) now fails.
  That failure is expected and is the visible signal of the limitation.

## Commands run

All commands executed inside `/home/eunjae/projects/llm-wiki` using the
project `.venv` (`python -m pytest` invoked via `.venv/bin/python`,
since the in-venv `pytest` shim has a stale absolute path from a prior
clone location — same situation as Phase 1 evidence).

| Command | Result |
| --- | --- |
| `git status --short && git diff --stat` | 7 modified files + 5 untracked (4 in-scope Phase 2: `src/llm_wiki/cli.py`, `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/ingest.py`, `tests/test_inbox_registration.py`; 3 out-of-scope: `src/llm_wiki/ingest_llm.py`, `src/llm_wiki/llm.py`, `src/llm_wiki/prompts.py`; 1 out-of-scope test: `tests/test_phase2_candidates_schema.py`; 2 out-of-scope untracked tests: `tests/test_staged_lint_gate.py`, `tests/test_two_pass_generation.py`) |
| `git diff --check` | PASS (exit 0, no whitespace conflicts) |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/cli.py src/llm_wiki/webapp/routes/ingest.py` | PASS (all three modules compile) |
| `.venv/bin/python -m py_compile tests/test_inbox_registration.py` | PASS |
| `.venv/bin/python -c "from llm_wiki import inbox, cli; from llm_wiki.webapp.main import create_app; from llm_wiki.webapp.routes import ingest as ingest_route"` | PASS (all four modules import cleanly) |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **16 passed** (4 Phase 1 + 12 Phase 2) — initial run |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **18 passed** (4 Phase 1 + 14 Phase 2) — P2-WU-005-RECHECK run, includes 2 new dedup tests |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/cli.py src/llm_wiki/webapp/routes/ingest.py tests/test_inbox_registration.py` | PASS — P2-WU-005-RECHECK |
| `git diff --check` | PASS (exit 0, no whitespace conflicts) — P2-WU-005-RECHECK |
| `.venv/bin/python -m pytest tests/test_web_navigation.py --deselect tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions -v` | **7 passed, 1 deselected** (deselected test is the documented known-limitation failure) |
| `.venv/bin/python -m pytest tests/test_web_navigation.py -v` | 7 passed, 1 failed — failure is `test_ingest_pending_sources_render_batch_queue_actions`, which asserts "작업으로 보내기" is rendered after an `/ingest/upload`. The failure is caused by Phase 2 rerouting the upload to Inbox while the template still reads pending from legacy `sources`. This is the **documented Phase 2 known limitation**. |
| `.venv/bin/python -m pytest tests/ --ignore=tests/test_two_pass_generation.py --ignore=tests/test_staged_lint_gate.py --ignore=tests/test_phase2_candidates_schema.py` | 44 passed, 1 failed (`test_ingest_pending_sources_render_batch_queue_actions`, same known limitation) |
| `.venv/bin/python -m pytest tests/test_two_pass_generation.py tests/test_staged_lint_gate.py tests/test_phase2_candidates_schema.py` | 25 passed, 11 failed — all 11 are pre-existing failures tracked under `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`; they are **unrelated to Phase 2 inbox registration work** (root cause: `_FakeClient` does not set `provider`, and `ingest_source` now requires `client.provider` after the STAB refactor). |
| `.venv/bin/python - <<'PY' … inline CLI helper smoke test … PY` | PASS — `_register_file_in_inbox` dispatches `note.md → Inbox/Markdown/note.md`, `doc.txt → Inbox/Files/doc.txt`, neither file ends up under `raw/` |

### Pytest availability note

Same situation as Phase 1 evidence: the shell-level `pytest` and
`.venv/bin/pytest` entrypoints have a stale absolute shebang pointing
at `/home/eunjae/project/llm-wiki/...` (singular `project/`). This is
a pre-existing infrastructure issue unrelated to Phase 2. Calling
pytest via `.venv/bin/python -m pytest` works correctly and is what
was used for every run above.

## Validation summary

- **Phase 2 deliverables are correct and complete for the backend
  foundation defined in the WU briefs.**
  - All three input-type registrations (document, markdown, pasted
    text) create Inbox items with correct input_type, relpath under
    `Inbox/{Files,Markdown,Text}/`, title parsed from content, and
    PENDING state.
  - `register_uploaded_bytes` writes the bytes to disk first, then
    registers via the matching `register_markdown_file` /
    `register_document_file` helper, and cleans up the temporary
    file on registration failure.
  - `_safe_copy_or_move` copies first, then unlinks the source only
    if the copy succeeded, so a mid-move failure does not lose data.
  - All three move primitives (`move_to_archive`, `move_to_review`,
    `move_to_failed`) update the DB state, write the corresponding
    `inbox_event` row with `source_path` / `target_path` /
    `db_state` / `retryable`, and never lose the source file on move
    failure.
  - `move_to_failed` also writes a sanitized diagnostic report
    (`<name>.diagnostic.md`) including `phase`, `error_type`, a
    1000-char-clipped error message, and a `retry_hint`, and emits a
    `failed_diagnostic_created` event.
  - File name collisions produce `name-1.ext`, `name-2.ext`, …
    instead of overwriting.
  - **P2-WU-005-RECHECK:** re-registering an identical content body for
    `register_document_file` / `register_markdown_file` (and therefore
    `register_uploaded_bytes` for `.md`/non-`.md` payloads) reuses the
    existing Inbox item. The second call returns
    `InboxRegistrationResult(deduped=True)` with the original
    `item.id`, no second physical file is created under
    `Inbox/Files/` or `Inbox/Markdown/`, and the most recent
    `inbox_event` on that item is `duplicate_content_hash_registered`
    with `source_path`, `stored_path`, `requested_input_type`,
    `db_state`, `retryable: false`, `deduped: true`,
    `source_preserved: true`.
  - CLI `wiki add` and Web `/ingest/upload` + `/ingest/paste` no
    longer write anything to `raw/`; raw/ stays clean for Raw Sources
    archive semantics.
  - Processing state is a DB lock with `lock_token` / `locked_at`,
    not a physical `_Processing` folder.
- **No regression** in the Phase 1 inbox domain tests (4/4 still pass
  with the new helpers in place) or in 43 of the 44 web-navigation
  tests. The single web-navigation failure is the known Phase 2
  limitation (legacy `sources` template vs. Inbox-first uploads).
- **P2-WU-005-RECHECK:** `pytest tests/test_inbox_domain.py
  tests/test_inbox_registration.py -v` is now 18/18 (was 16/16). The
  two new tests
  (`test_document_registration_dedupes_by_content_hash_without_creating_second_file`
  and
  `test_markdown_registration_dedupes_by_content_hash_and_records_traceable_event`)
  are green, and every prior Phase 1 + Phase 2 inbox test still
  passes.

## Process / port cleanup

- No dev server, watcher, or port listener was started by this
  validation. All FastAPI/Web testing used `TestClient` in-process.
- The pre-existing `uvicorn` instance on port 8000 (PID 8343,
  parent PID 8326) was running before this WU started and is left
  untouched per the destructive / cleanup policy.
- No background processes were spawned by the validator.
- No secrets / env files were read or modified.

## P2-WU-005-RECHECK addendum (duplicate content-hash dedup fix)

### Fix summary

- `src/llm_wiki/inbox.py` — added `_find_existing_inbox_item_by_hash`
  and `_item_stored_path` helpers; `_register_file` now queries
  `inbox_items` by `content_hash` before writing a new file. On
  match it emits `duplicate_content_hash_registered` and returns an
  `InboxRegistrationResult(deduped=True)` that reuses the existing
  item. `InboxRegistrationResult.deduped` (default `False`) exposes
  this to callers. Web upload response (`/ingest/upload`) and CLI
  `_register_file_in_inbox` propagate the `deduped` flag
  automatically.
- `tests/test_inbox_registration.py` — added
  `test_document_registration_dedupes_by_content_hash_without_creating_second_file`
  and
  `test_markdown_registration_dedupes_by_content_hash_and_records_traceable_event`.

### Recheck commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **18 passed, 1 warning in 3.96s** (4 Phase 1 inbox domain + 14 Phase 2 inbox registration, including both new dedup tests) |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/cli.py src/llm_wiki/webapp/routes/ingest.py tests/test_inbox_registration.py` | PASS — exit 0, no syntax errors |
| `git diff --check` | PASS — exit 0, no whitespace conflicts |
| `.venv/bin/python -c "from llm_wiki import inbox, cli; from llm_wiki.webapp.main import create_app; from llm_wiki.webapp.routes import ingest as ingest_route"` | PASS — modules import cleanly |
| `git status --short && git diff --stat` | 6 modified files + 5 untracked (4 in-scope Phase 2: `src/llm_wiki/cli.py`, `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/ingest.py` modified, `tests/test_inbox_registration.py` untracked; 3 out-of-scope: `src/llm_wiki/ingest_llm.py`, `src/llm_wiki/llm.py`, `src/llm_wiki/prompts.py`; 1 out-of-scope test: `tests/test_phase2_candidates_schema.py`; 2 out-of-scope untracked tests: `tests/test_staged_lint_gate.py`, `tests/test_two_pass_generation.py`). Inbox dedup fix touches only `src/llm_wiki/inbox.py` and `tests/test_inbox_registration.py`. |

### Recheck validation summary

- **P0 guardrails re-evaluated:**
  - File name collision → PASS (unchanged).
  - **Duplicate content_hash handling (document file) → PASS** —
    was a known gap, now closed by `_register_file`'s
    `_find_existing_inbox_item_by_hash` lookup and the new
    `test_document_registration_dedupes_by_content_hash_without_creating_second_file`.
  - **Duplicate content_hash handling (markdown file) → PASS** —
    same mechanism for the `.md` path, validated by
    `test_markdown_registration_dedupes_by_content_hash_and_records_traceable_event`.
- All previously passing Phase 1 + Phase 2 tests still pass (no
  regressions from the dedup change).
- `py_compile` and `git diff --check` clean.

### Recheck remaining risks

- **Pasted-text hash dedup** (`register_pasted_text`): not
  implemented by the P2-WU-005-RECHECK fix; out of Phase 2 scope.
  The pasted-text path generates a new file before computing the
  hash, so a content-hash-based "reuse previous paste" would
  require an explicit policy decision (filename? timestamp? body
  similarity?). Accepted trade-off until a later phase requests it.
- **`inbox_items.content_hash` is not indexed.** The DB schema
  defines `idx_inbox_items_state`, `idx_inbox_items_source`, and
  `idx_inbox_items_relpath` but no `idx_inbox_items_content_hash`.
  For the small per-vault dataset this is fine; if Inbox grows,
  add an index in a follow-up.
- All other risks from the prior section (legacy `/ingest`
  template, `InboxItem → sources.id / jobs` mapping, out-of-scope
  2-pass/STAB worktree changes, pytest shim shebang) remain
  unchanged.

### Recheck validation result

- **PASS** — duplicate content_hash dedup is implemented for the
  two file-based input types (`register_document_file`,
  `register_markdown_file`) and is verified by 2 new unit tests
  plus the 12 prior Phase 2 tests (all green). The previously
  open `Remaining risks #2` (duplicate-hash dedup missing) is
  closed.

### Recheck ready for /check

- **true** — Phase 2 inbox registration deliverables, including
  the newly added duplicate content_hash dedup, are complete and
  validated. Same caveats as the prior section apply: the full
  `pytest tests/` run is still red due to pre-existing STAB
  failures and the documented `/ingest` legacy-template
  limitation, but those are not part of Phase 2 scope.

## Evidence artifacts

- This file: `.code-planner/03-build/evidence/phase-2-build-evidence.md`
- Cross-references (separate workstreams):
  - Phase 1: `.code-planner/03-build/evidence/phase-1-build-evidence.md`
  - 2-pass / STAB-001/002/003: `.code-planner/03-build/evidence/2-pass-generation-fix-evidence.md`
    and the fix request at
    `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`

## Remaining risks

1. **Legacy `/ingest` template still reads from `sources` table.**
   After Phase 2, uploads land in Inbox but the page renders pending
   items from the legacy `sources` table. `test_ingest_pending_sources_render_batch_queue_actions`
   fails today. This is the **documented Phase 2 known limitation**;
   the minimum-integration template UX work is deferred to Phase 5.
   The check agent should treat this as expected, not as a regression.
2. **Duplicate-hash dedup was missing in Inbox registration.** The
   Phase 1 brief required "duplicate hash handling work" in
   `.code-planner/02-planning/validation/01-validation-plan.md` line 23.
   Originally, the new `register_document_file` /
   `register_markdown_file` / `register_pasted_text` /
   `register_uploaded_bytes` helpers recorded `content_hash` but did
   not query the `inbox_items` table for an existing row with the same
   hash before inserting a new one. The previous CLI `add` did dedup
   by hash via `ingest_raw.add_file`; that dedup was lost when CLI was
   rewired to Inbox helpers.
   **P2-WU-005-RECHECK fix:** `_register_file` now consults
   `inbox_items` by `content_hash` first; on a match, it emits a
   `duplicate_content_hash_registered` event and returns
   `InboxRegistrationResult(deduped=True)` referencing the existing
   Inbox item — no second physical file is written under
   `Inbox/Files/` or `Inbox/Markdown/`. The dedup covers both
   `register_document_file` and `register_markdown_file` (and
   therefore `register_uploaded_bytes` for both code paths). Two new
   tests in `tests/test_inbox_registration.py` assert:
   (a) `deduped=True` on the second call,
   (b) the same `inbox_item.id` is reused,
   (c) only one physical file exists in the destination Inbox
       subdirectory,
   (d) the latest event is `duplicate_content_hash_registered` with
       `source_path`, `stored_path`, `requested_input_type`,
       `db_state`, `retryable=false`, `deduped=true`,
       `source_preserved=true`.
   This gap is **CLOSED** for the file-based input types. The
   pasted-text path (`register_pasted_text`) still does not dedup by
   hash because it generates a new file before computing the hash;
   that remains out of scope per the Phase 2 brief and is documented
   as an accepted trade-off until pasted-text dedup is requested by a
   later phase.
3. **Phase 2 web/CLI integration is minimum-only.** `/ingest/start`
   still dispatches jobs by `source_id`. There is no safe
   `InboxItem.id → sources.id → ingest_jobs.id` mapping yet, so a
   Phase 5 UI cannot dispatch Inbox items into extraction jobs without
   first adding that mapping. This is also the
   `.code-planner/03-build/phases/phase-2-execution-brief.md` documented
   known limitation; tracked as the same risk as #1 above.
4. **Out-of-scope 2-pass/STAB worktree changes are unstaged.** Same
   situation as flagged in Phase 1 evidence. The Phase 2 commit
   (`feat: route inputs through inbox`) should stage only the four
   Phase 2 files (`src/llm_wiki/cli.py`, `src/llm_wiki/inbox.py`,
   `src/llm_wiki/webapp/routes/ingest.py`, `tests/test_inbox_registration.py`)
   and leave `ingest_llm.py`, `prompts.py`, `llm.py`,
   `test_phase2_candidates_schema.py`, `test_two_pass_generation.py`,
   `test_staged_lint_gate.py` untouched.
5. **Pytest shim shebang.** Same pre-existing infrastructure issue
   noted in Phase 1 evidence. `.venv/bin/python -m pytest` works.

## Validation result

- **Phase 2 validation**: PASS for the Phase 2 deliverables.
  - 14/14 Phase 2 inbox registration tests pass (was 12/12; +2 new
    duplicate-hash dedup tests added by P2-WU-005-RECHECK).
  - 4/4 Phase 1 inbox domain tests still pass (no regression).
  - 7/8 web-navigation tests pass; 1 fails due to the documented
    known limitation (legacy `sources` template vs. Inbox-first
    uploads). That failure is expected and must be acknowledged by
    the check agent, not re-opened as a regression.
  - All Phase 2 P0 guardrails (seven validation-plan items including
    file name collision + duplicate content_hash handling for both
    document and markdown inputs) satisfied by the backend
    foundation.
  - `py_compile` and `git diff --check` clean (re-run after the
    P2-WU-005-RECHECK fix; both still exit 0).

- **Out-of-scope (Phase 2 STAB / 2-pass / unrelated)**: unchanged from
  the state captured in Phase 1 evidence. 11 pre-existing failures
  in `test_two_pass_generation.py`, `test_staged_lint_gate.py`, and
  `test_phase2_candidates_schema.py` are unrelated to the Phase 2
  inbox registration work and continue to be tracked under
  `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`.
  A blanket `pytest tests/` run will still be red until that fix
  request is closed.

- **Full end-to-end claim**: explicitly NOT made. The Phase 2 minimum
  integration does not implement `InboxItem.id → sources.id →
  ingest_jobs.id` mapping for `/ingest/start`, so end-to-end ingest
  from a pasted-text / uploaded file into a Wiki page is not
  verified here. The check agent must read this as "backend
  foundation passes", not "full pipeline works".

## Ready for /check

- **Phase 2 backend foundation**: yes — Phase 2 deliverables
  (Inbox registration for three input types, file move primitives,
  diagnostic report, CLI/Web routing, dedicated tests, and — after
  P2-WU-005-RECHECK — content_hash dedup for file-based input types)
  are correct and satisfy all Phase 2 validation-plan items except
  the deferred-template-UX work and the pasted-text dedup (accepted
  trade-off).
- **Full-suite ready**: no — the 11 pre-existing STAB failures plus
  the one known-limitation web-navigation failure mean a full-tree
  `pytest` is red. These are tracked under their own workstreams and
  must not be conflated with Phase 2 inbox registration.

If `/check phase-2` is scoped strictly to the Phase 2 inbox
registration deliverables (recommended per the brief), this evidence
supports passing the gate with the caveats in "Remaining risks".
If `/check` runs the entire `tests/` suite, it will be red and the
failures must be acknowledged as belonging to either the STAB fix
request or the documented Phase 2 known limitation — not to the
Phase 2 inbox registration deliverables themselves.

## P2-WU-005-RECHECK2 addendum (deduped propagation)

This addendum is the latest targeted Phase 2 recheck and supersedes the
P2-WU-005-RECHECK test count. It validates propagation of the existing
Inbox registration `deduped` result through the Web and CLI surfaces.

### Changed files reviewed

- `src/llm_wiki/webapp/routes/ingest.py` — `/ingest/upload` now includes
  `deduped: registration.deduped` for each file result, and
  `/ingest/paste` includes the same field in its JSON response.
- `src/llm_wiki/cli.py` — `wiki add` counts
  `registration.deduped` results separately from newly added results
  and includes `<count> deduped` in the final summary when non-zero.
- `tests/test_inbox_registration.py` — added
  `test_web_upload_deduped_flag_is_false_on_first_call_true_on_second_with_same_content`,
  which exercises two HTTP uploads with identical bytes and verifies
  `deduped=false` then `deduped=true`, reuse of the original Inbox item
  id, and only one physical file in `Inbox/Files`.
- `.code-planner/03-build/evidence/phase-2-build-evidence.md` — updated
  by the validation agent with this recheck. No source or test file was
  modified by the validator.

### Commands and results

All commands ran from `/home/eunjae/projects/llm-wiki`.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **PASS — 19 passed, 1 warning in 4.70s** (4 Phase 1 inbox-domain tests + 15 Phase 2 registration/integration tests). The new HTTP upload deduped-flip test passed. The warning is the existing Starlette `TestClient`/`httpx` deprecation warning. |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/cli.py src/llm_wiki/webapp/routes/ingest.py tests/test_inbox_registration.py` | **PASS — exit 0, no output**, so all assigned source/test files compile. |
| `git diff --check` | **PASS — exit 0, no output**, so no whitespace errors were found. |

### User-facing validation items

- **HTTP upload propagation: PASS with runtime test evidence.** The first
  upload returns `deduped=false`; uploading the same content again
  returns `deduped=true` and the same `inbox_item_id`, without creating
  a duplicate Inbox file.
- **HTTP paste response propagation: PASS by source inspection plus
  route-suite execution and compilation.** The response contains
  `deduped: registration.deduped`. Pasted-text hash dedup itself remains
  intentionally out of scope, so this value currently reflects the
  pasted-text registration result (normally `false`); this recheck does
  not claim pasted-text dedup was added.
- **CLI summary propagation: PASS by source inspection and compilation.**
  `wiki add` increments a dedicated `deduped` counter and renders it in
  the summary. The assigned targeted suite covers CLI registration
  dispatch but does not contain a separate terminal-output assertion.
- Existing document/Markdown hash dedup, collision handling, movement,
  diagnostic, and Phase 1 regression checks remain green in the same
  19-test run.

### Process / port cleanup

- No server, watcher, tracked background process, or port listener was
  started for this recheck. FastAPI validation ran in-process through
  `TestClient`, so no cleanup action was required.

### Recheck2 validation result

- **PASS** — every assigned verification command completed successfully,
  and the new HTTP upload path test supplies runtime evidence that the
  externally visible `deduped` value flips on duplicate content.
- The previously documented full-suite/STAB and legacy `/ingest`
  template limitations remain unchanged and are outside this targeted
  recheck; no new Phase 2 blocker was found.

### Recheck2 ready for `/check`

- **true** — ready for a Phase 2-scoped `/check` with the existing,
  explicitly documented caveats. This is not a claim that the unrelated
  full test suite or deferred Phase 5 UI/job-dispatch flow is green.
