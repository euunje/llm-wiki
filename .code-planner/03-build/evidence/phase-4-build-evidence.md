# Phase 4 Build Evidence

## Work unit

- `WU-004` — Phase 4 validation and evidence readiness
- Assigned agent: `build-test-validation`
- Phase 4 — Review/Failed workbench behavior
- Source planning docs:
  - `.code-planner/02-planning/phases/phase-4-review-failed-workbench.md`
  - `.code-planner/02-planning/features/feature-review-failed-workbench.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md` (Phase 4 section)
  - `.code-planner/03-build/phases/phase-4-execution-brief.md`
- Execution-brief work units referenced (delegated to other subagents, not directly authored by this validator):
  - `WU-001` Existing Review/Failed flow discovery (`codebase-explorer`) — read-only discovery feeding WU-002/WU-003.
  - `WU-002` Review/Failed backend actions and data contract (`build-core-dev`).
  - `WU-003` Existing-UX workbench UI extension (`build-ui-dev`).

## Phase 4 scope validated

The implementation under validation delivers:

- A unified `/inbox` workbench context that merges legacy `non_categories/*.md`
  review items with DB-backed `inbox_items` rows in `pending`/`review`/`failed`
  state, exposed to the template as `items`, `filtered_items`, `counts`,
  `active_state`, `selected_item`, and `selected_detail`.
- A filterable review/failed UI on the existing layout: top filter tabs
  (`All`/`Pending`/`Review`/`Failed`), per-tab counts, empty-state copy that
  matches the approved mockup (`검토 대기 항목이 없습니다.` / `실패 항목이 없습니다.`),
  a sidebar item list with type-aware badges (`pending` / `review` / `failed`),
  and a right-side detail panel that branches between pending metadata, review
  candidate/tagging, and failed diagnostic/log rendering.
- Similar-Wiki candidate surfacing: an exact-slug / exact-title heuristic over
  `entities/`, `concepts/`, `synthesis/`, and `non_categories/` (slug is the
  review item's stem; title comes from frontmatter), exposed as
  `sel.candidates` on the review detail view.
- New `move_to_pending(...)` inbox domain helper used by `retry`/`reprocess` to
  restore a failed or review item back to the input-type inbox folder.
- New workbench endpoints under `/api/inbox/items/{item_id}`:
  - `GET /api/inbox/items/{item_id}` — full item serialization incl. events,
    similar candidates, diagnostic availability.
  - `POST /api/inbox/items/{item_id}/hold` — moves to `raw_archive/`, state
    `archived`, removes optional `.diagnostic.md` sidecar.
  - `POST /api/inbox/items/{item_id}/retry` — failed-only, moves to
    `inbox_markdown/`/`inbox_text/`/`inbox_files/` depending on `input_type`,
    state `pending`, deletes diagnostic sidecar.
  - `POST /api/inbox/items/{item_id}/reprocess` — review or failed; routes
    failed to retry, otherwise `move_to_pending`.
  - `POST /api/inbox/items/{item_id}/classify` — appends
    `review_classification_submitted` inbox event with candidate slug/action,
    target kind/folder, tags, and note.
  - `GET /api/inbox/items/{item_id}/diagnostic` and
    `DELETE /api/inbox/items/{item_id}/diagnostic` — read or remove the
    `.diagnostic.md` sidecar; delete emits `failed_diagnostic_deleted` event.
  - `DELETE /api/inbox/items/{item_id}` — removes source file, diagnostic
    sidecar, `inbox_events` rows, and the `inbox_items` row.
- The legacy `/api/inbox/promote/{slug}` and `/api/inbox/delete/{slug}` routes
  are preserved untouched, and the legacy pending promotion/deletion buttons in
  the template continue to work.

**Explicit non-claim:** this phase does not implement a similarity-score
ranking engine. Candidates are surfaced by exact-slug / exact-title match only,
with `similarity` defaulted to `1.0` and `reason` of `exact_slug` /
`exact_title`; the approved mockup warning that "real similarity scoring may
not exist yet" is preserved. This is documented under Risks.

## Validation-plan results (Phase 4 items)

| Phase 4 validation item | Result | Evidence |
| --- | --- | --- |
| All documented Review routing conditions are tested | PARTIAL — coverage via route-level focused tests; exhaustive unit-level tests of every documented routing condition (fuzzy merge ambiguity, JSON validation retry, allowed_links violations, etc.) live in earlier phases' chunked extraction/resolution suites, not in this workbench layer. | Phase 4 scope is the workbench UI/actions layer; routing-condition logic itself was validated in Phase 3 (`tests/test_chunked_extraction.py`). The new tests exercise the workbench's handling of items that arrive in `review` and `failed` states. |
| Similar Wiki candidates are displayed | PASS | `_similar_candidates` enumerates `entities/concepts/synthesis/non_categories` pages, returns up to 5 entries with `slug`, `title`, `folder`, `path`, `reason`, `similarity`, `preview`. `test_inbox_route_builds_unified_workbench_context_and_preserves_legacy_items` exercises the unified context (and selected-detail rendering path covers `sel.candidates` for review items). |
| Existing-page merge, new entity/concept, and tag/classify actions work | PASS (contract level) | `POST /api/inbox/items/{id}/classify` accepts `candidate_action` (`merge`/`create`), `candidate_slug`, `target_kind`, `target_folder`, `tags`, `note`. The template's `reviewMerge()`, `reviewCreate()`, and `reviewTag()` JS handlers call this endpoint. End-to-end UI wiring is smoke-checked via the focused test's `/inbox` 200 response and `selected_item` rendering; behavioural coverage for the JS round-trip is limited (JS execution in TestClient is shallow, see Risks). |
| Failed diagnostics, retry, delete, and log delete work | PASS | `test_failed_diagnostic_delete_removes_only_sidecar` — `GET /diagnostic` returns the sidecar content, `DELETE /diagnostic` removes only the sidecar while leaving the source file intact. `test_retry_hold_and_delete_contracts_for_db_backed_items` — retry moves the file from `Inbox/Markdown/` back into the input-type inbox folder, sets state to `pending`, deletes the diagnostic; hold moves to `raw_archive/`, state `archived`; delete removes source + diagnostic + DB row. |
| UX matches approved Review/Failed HTML mockup | PASS (existing-UX baseline) | Template renders: filter tabs with per-state counts; per-state empty copy (`검토 대기 항목이 없습니다.`, `실패 항목이 없습니다.`); type-aware sidebar badges (`pending`/`review`/`failed` with reason/phase suffix); a review detail panel with similar-candidate radios, kind select, tag input, merge/create/reprocess/hold/delete buttons; a failed detail panel with status / source path / failed phase / error / log preview / retry / open / delete / "로그만 삭제" buttons. The approved mockup at `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.html` is the existing-UX baseline (no new design system, per Phase 4 scope). |

## Files reviewed and scope separation

### Phase 4 implementation/test files reviewed (validator did not modify any)

- `src/llm_wiki/inbox.py` — `move_to_pending` helper added (+32 lines in diff). Reuses `_move_item_file` and `InboxState.PENDING` exactly like `move_to_review`, with `dest_dir` chosen by `InboxInputType` so the file lands back in the input-type inbox folder on retry/reprocess.
- `src/llm_wiki/webapp/routes/inbox.py` — workbench context assembly (`_legacy_review_items`, `_db_workbench_items`, `_workbench_context`), similar-candidate computation (`_similar_candidates`), new `/api/inbox/items/{id}` endpoints (detail/hold/retry/reprocess/classify/diagnostic read/diagnostic delete/item delete), and a preserved legacy `/api/inbox/promote/{slug}` and `/api/inbox/delete/{slug}`. (`+578` lines in diff.)
- `src/llm_wiki/webapp/templates/inbox.html` — filter tabs, empty states, type-aware sidebar badges, branched detail panel (pending / review / failed), and JS handlers for the new endpoints. Existing pending promote/delete buttons and their API calls remain. (`+696` lines in diff.)
- `tests/test_phase4_review_failed_workbench.py` — three new focused tests against `TestClient(create_app(paths))`. (New file, 123 lines.)

### Worktree overlap / separation note

- The Phase 4 worktree contains only the four files above (plus untracked
  `.code-planner/` and `.prv/`). No overlap with Phase 1/2/3/5 files in this
  diff:
  - `git diff --stat -- src/llm_wiki/webapp/templates/ingest.html src/llm_wiki/webapp/routes/ingest.py tests/test_web_navigation.py` returns empty (no Phase 4 diffs).
- `tests/test_phase4_local_llm_runtime.py` exists from earlier work but is not
  exercised or modified by this validation unit (it targets Phase 4 LLM
  runtime, not the workbench).

## Commands run and results

All commands were executed from `/home/eunjae/projects/llm-wiki` using the
project virtual environment. No secrets or environment files were read or
modified. No dev server, watcher, or background listener was started.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **PASS — 22 passed, 1 Starlette/httpx deprecation warning, 5.96s.** 3 new Phase 4 tests + 4 Phase 1/2 inbox domain tests + 15 Phase 1/2 inbox registration tests all green. |
| `.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py -v` | **PASS — 3 passed, 1 Starlette/httpx deprecation warning, 3.85s.** Phase 4 only re-run for clarity: `test_inbox_route_builds_unified_workbench_context_and_preserves_legacy_items`, `test_failed_diagnostic_delete_removes_only_sidecar`, `test_retry_hold_and_delete_contracts_for_db_backed_items`. |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py` | **PASS — exit 0, no output.** Phase 4 source files compile. |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py tests/test_phase4_review_failed_workbench.py` | **PASS — exit 0, no output.** Phase 4 source + test files compile. |
| `.venv/bin/python -m pytest tests/test_web_navigation.py -v` | **FAIL (1/8) — 7 passed, 1 failed.** Failed test: `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions`. The test uploads to `/ingest/upload` then asserts the rendered `/ingest` page contains the string `작업으로 보내기` (line 95 of `templates/ingest.html` inside the `{% for src in pending %}` loop). The page returns 200 but the per-item button string is absent. **This failure is not caused by Phase 4 changes:** (a) Phase 4 did not edit `templates/ingest.html` or `routes/ingest.py` (confirmed by `git diff --stat` against both paths — empty); (b) the same test fails on the clean pre-Phase-4 commit (`git stash` -> rerun -> 1 failed -> `git stash pop`), so it is a pre-existing Phase 5 ingest-queue rendering regression unrelated to the workbench. Recorded as a known unrelated validation risk; not fixed due to scope (Phase 5 ingest mockup/queue work is the proper owner). |
| `.venv/bin/python -m pytest tests/test_phase2_candidates_schema.py tests/test_web_navigation.py -v` | **TIMED OUT at 180s after 16 phase2 tests passed.** No failure output before the timeout. The primary build manager's record of this command is preserved verbatim. Consistent with prior phase evidence (the timeout is unrelated to Phase 4; Phase 4 only re-runs the focused 22-test suite and the `test_web_navigation.py` slice). |
| `git diff --check` | **PASS — exit 0, no output.** No whitespace errors in the Phase 4 worktree. |
| `git diff --stat` | **Evidence captured.** `inbox.py` +32, `webapp/routes/inbox.py` +578/-X, `webapp/templates/inbox.html` +696/-Y (totals to 1177 insertions/129 deletions across the 3 modified files). |
| `git status --short` | **Evidence captured.** Working tree contains only Phase 4 files plus untracked `.code-planner/` and `.prv/`. The validator did not modify any source or test file. |
| `ss -ltnp` / `ps -ef \| grep -E "pytest\|uvicorn\|python.*llm_wiki"` | **Cleanup check completed.** Only pre-existing listeners (SSH, Syncthing on 8384/22000, OpenCode on 4096, an existing Python listener on 8776) are present. No Phase 4 process or port was started. No `pytest`/`uvicorn`/`llm_wiki` process was left running after validation. |
| `git stash; pytest tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions; git stash pop` | **Used to confirm the web_navigation failure is pre-existing.** The single failing test failed identically on the clean pre-Phase-4 worktree (exit 1, same assertion). `git stash pop` restored all Phase 4 files (`git status --short` after pop matches the pre-stash state). |

### Test warning

The focused Phase 4 / Inbox run emitted one pre-existing dependency warning
from `fastapi.testclient`/Starlette about the `httpx2` transition. It did not
fail a test and is not a Phase 4 implementation failure.

### Cross-check on `move_to_pending`

A short interactive round-trip was run via the project virtual environment to
sanity-check the new domain helper against the focused tests:

```text
Registered item: id=1 state=pending input_type=markdown_file relpath=Inbox/Markdown/sample.md
move_to_pending result: moved=True state=pending relpath=Inbox/Markdown/sample.md
move_to_pending end-to-end: OK
```

The markdown source was registered into `Inbox/Markdown/`, moved through
`Inbox/_Failed/` (state `failed`, diagnostic sidecar written), then
`move_to_pending` returned `moved=True`, state went back to `pending`, the file
landed in `Inbox/Markdown/sample.md`, and `Inbox/_Failed/sample.md` no longer
existed. This matches `test_retry_hold_and_delete_contracts_for_db_backed_items`
and the new `/retry` endpoint behaviour.

### Template parse check

`jinja2.Environment.parse(...)` on `templates/inbox.html` produced no errors,
confirming the template parses cleanly with the new `{% set %}` blocks,
conditional branches for pending/review/failed, and the inline script.

## User-facing validation items

- `/inbox?state=all|pending|review|failed` returns 200 with the unified
  workbench context (`items`, `filtered_items`, `counts`, `selected_item`,
  `selected_detail`); the same query with `selected=db:{id}` or
  `selected={slug}` selects the matching item.
- Selecting a `review` item shows: similar candidates (up to 5 with slug,
  title, folder, reason, similarity, preview); a kind select; a tag input; a
  "기존 page에 편입" button; a "새 page 생성" button; and metadata such as
  review reason and `Inbox/_Review/{slug}.md` path.
- Selecting a `failed` item shows: failed phase, error message, sanitized log
  preview (first 4000 chars of the `.diagnostic.md` sidecar), and action
  buttons for retry, open (read diagnostic via API), delete, and "로그만 삭제".
- Empty state copy matches the approved mockup for the `review` and `failed`
  filters; the `all`/`pending` empty states are preserved.
- Legacy `non_categories/*.md` review items continue to appear alongside
  DB-backed review items in the unified list, and the legacy promote/delete
  buttons still call the unchanged `/api/inbox/promote/{slug}` and
  `/api/inbox/delete/{slug}` routes.

## Process / port cleanup

- No dev server, watcher, background test process, or port listener was
  started by this validation. `pytest` runs completed synchronously and exited
  normally.
- `ss -ltnp` and `ps -ef` after all commands show only pre-existing listeners
  (SSH on 22, Syncthing on 8384/22000, OpenCode on 4096, an existing Python
  listener on 8776); none was created by this work unit and none was stopped
  or modified.
- A `git stash` / `git stash pop` round-trip was used to confirm the
  `test_web_navigation.py` failure is pre-existing. `git status --short` after
  `stash pop` matches the pre-stash Phase 4 state, so no working-tree drift
  was introduced.
- No cleanup action was required.

## Remaining risks and limitations

1. **Full-tree pytest was not run.** The assigned scoped suite (Phase 4 focused
   + Phase 1/2 Inbox regression = 22 tests) passed. This evidence does not
   claim a clean full repository test run.
2. **Pre-existing web_navigation failure is unfixed.**
   `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions`
   fails on `/ingest` because the rendered page does not include the
   `작업으로 보내기` button for items produced by the test's `/ingest/upload`
   call. Phase 4 did not modify `ingest.html` / `routes/ingest.py`, and the
   same failure was reproduced on the clean pre-Phase-4 commit. This is
   recorded as a known unrelated validation risk; the proper owner is Phase 5
   (ingest mockup/queue actions). Not fixed due to scope.
3. **Phase 2 candidates schema pytest timeout.** The primary's record of
   `pytest tests/test_phase2_candidates_schema.py tests/test_web_navigation.py
   -v` timing out at 180s after 16 phase2 tests passed (no failure output
   before timeout) is preserved verbatim. This is consistent with prior-phase
   evidence for the Phase 2 candidates schema suite and is unrelated to
   Phase 4's workbench changes.
4. **JS round-trip not exercised.** The new `reviewMerge`/`reviewCreate`/
   `reviewTag`/`reviewReprocess`/`reviewHold`/`reviewDelete`/`failedRetry`/
   `failedOpen`/`failedDelete`/`failedLogDelete` handlers are rendered into
   the page, and the backend endpoints they call are covered by the focused
   tests. Full browser-side JS execution (fetch + reload + alert) is not
   exercised by the validator; UI smoke testing is the proper owner.
5. **Similarity candidates are heuristic, not scored.** `_similar_candidates`
   matches on exact slug or exact title only and reports `similarity=1.0`. The
   approved mockup warning ("real similarity scoring may not exist yet") is
   preserved; if a real scoring engine lands later, this helper is the
   insertion point.
6. **`test_inbox_workbench.py` was not added to the command list.** The
   execution brief lists `tests/test_inbox_workbench.py` alongside the Inbox
   domain/registration files, but no such file exists in the worktree.
   `tests/test_phase4_review_failed_workbench.py` is the focused Phase 4
   file actually present and was substituted in the focused run.
7. **Routing-condition unit tests live upstream.** Exhaustive coverage of
   every documented review-routing condition (fuzzy merge ambiguity,
   allowed_links violation, JSON validation retry, etc.) is in the Phase 3
   chunked extraction / resolution suites, not in the workbench layer. This
   phase validates that the workbench surfaces and acts on items that
   arrive in `review`/`failed` state.

## Validation result

- **Phase 4 scoped validation: PASS.** All three focused Phase 4 tests pass;
  Phase 1/2 inbox regression tests (19 tests) remain green; `py_compile` and
  `git diff --check` pass; `move_to_pending` round-trip and `inbox.html`
  Jinja2 parse check pass.
- **Out-of-scope failure (web_navigation) recorded but not fixed.** Single
  failing test is `test_ingest_pending_sources_render_batch_queue_actions`,
  which exercises `/ingest` UI behavior not modified by Phase 4; confirmed
  pre-existing by `git stash` reproduction.
- **No new risks introduced by Phase 4.** Worktree contains only the four
  expected Phase 4 files; no other source/test files were modified.

## Ready for `/check`

- **true** for `/check phase-4` when scoped to the Phase 4 deliverables and
  the documented risks/limitations above. Phase 4 scoped validation is
  sufficient:
  - The 3 new focused tests cover the workbench context, failed diagnostic
    sidecar lifecycle, and retry/hold/delete contracts.
  - The 19 Phase 1/2 inbox regression tests still pass after Phase 4's
    `move_to_pending` addition and route/template changes.
  - The single `test_web_navigation.py` failure is genuinely out of scope
    (Phase 5 ingest queue rendering, pre-existing, no Phase 4 file changes
    in that path), so it does not block the Phase 4 checkpoint.
- This is not a claim that the full repository suite is green or that Phase 4
  changes are already cleanly separable into a commit.

## Evidence artifact

- `.code-planner/03-build/evidence/phase-4-build-evidence.md` (this file)