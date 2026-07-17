# Phase 1 Build Evidence

## Work unit

- WU-004: Phase 1 validation and evidence readiness
- Phase 1 — Inbox domain model and path/state foundation
- Source planning docs:
  - `.code-planner/02-planning/phases/phase-1-inbox-domain.md`
  - `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
  - `.code-planner/02-planning/features/feature-inbox-domain.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md`
  - `.code-planner/03-build/phases/phase-1-execution-brief.md`

## Phase 1 scope (per planning docs)

- Define `inbox_items` / events schema; idempotent migration preserving
  existing `sources` / `jobs` / `runs`.
- Inbox state enum: `pending`, `processing`, `failed`, `review`, `archived`,
  `ingested`.
- Path semantics for Inbox root, `_Failed`, `_Review`, Raw Sources archive.
- `processing` must be a DB state / lock, not a physical folder.
- Default and Ja vault layout compatibility, including `non_categories`-based
  tests.

Explicitly out of scope for Phase 1:

- Actual Web UI changes.
- Real Inbox registration / file movement flow.
- Failed / Review action implementation.
- Chunked extraction.

## Files in Phase 1 scope (changes validated)

- `src/llm_wiki/db.py` — `SCHEMA_VERSION 3 -> 4`, added `inbox_items`,
  `inbox_events` tables with state / source / relpath indexes.
- `src/llm_wiki/config.py` — added `INBOX_DIR`, `INBOX_SUBDIRS`, the
  `default_inbox_dirs()` helper, and `WikiPaths` properties:
  `inbox`, `inbox_files`, `inbox_markdown`, `inbox_text`, `inbox_failed`,
  `inbox_review`, plus a `raw_archive` alias equal to `raw`.
- `src/llm_wiki/scaffold.py` — `scaffold()` creates the Inbox root and its
  subdirectories (Files, Markdown, Text, _Failed, _Review) with `.gitkeep`.
- `src/llm_wiki/inbox.py` (new) — domain helpers: `InboxState`, `InboxInputType`
  enums; `InboxItem` / `InboxEvent` dataclasses; CRUD helpers
  `create_inbox_item`, `get_inbox_item`, `list_inbox_items`,
  `append_inbox_event`, `list_inbox_events`, `transition_inbox_item`.
- `tests/test_inbox_domain.py` (new) — 4 tests covering the Phase 1 contract.

## P0 guardrail verification

| Validation plan item                                               | Status | Evidence |
| ------------------------------------------------------------------ | ------ | -------- |
| DB migration is idempotent                                         | PASS   | `test_init_db_migration_is_idempotent_and_preserves_existing_rows` |
| Existing sources / jobs / runs preserved                           | PASS   | same test asserts `sources` row + `ingest_runs` row preserved after 2x `init_db` |
| Inbox state enum matches docs and code                             | PASS   | `test_inbox_states_and_helpers_follow_phase1_contract` asserts the exact 6-value enum |
| Default layout (`Inbox/...`) passes                                | PASS   | `test_wikipaths_exposes_inbox_path_semantics_and_respects_non_categories` (default branch) |
| Ja layout (`00. Inbox/_Review`) passes                             | PASS   | same test (Ja branch via `page_dirs.non_categories = "00. Inbox/_Review"`) |
| Existing `non_categories`-based tests have a clear migration path  | PASS   | `WikiPaths.inbox_review == WikiPaths.non_categories` on Ja layout |
| `processing` is DB state / lock, not a physical `_Processing` folder | PASS | `test_scaffold_creates_inbox_dirs_but_not_processing` and Ja-layout branch |

## Commands run

All commands executed inside `/home/eunjae/projects/llm-wiki` using the project
`.venv` (`python -m pytest` invoked via `.venv/bin/python`, since the in-venv
`pytest` shim has a stale absolute path from a prior clone location).

| Command | Result |
| ------- | ------ |
| `git status --short && git diff --stat` | 7 modified files, 3 untracked files (see "Scope note" below) |
| `git diff --check` | PASS (no whitespace conflicts) |
| `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/db.py src/llm_wiki/config.py src/llm_wiki/scaffold.py` | PASS |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py -v` | **4 passed** |
| `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_phase1_runtime_mcp_changelog.py tests/test_phase3_fresh_start_guidance.py tests/test_parsers.py tests/test_relinking.py tests/test_korean_default_prompts.py` | **20 passed** (zero regression after schema bump) |
| `.venv/bin/python -c "from llm_wiki.db import SCHEMA_VERSION, SCHEMA_SQL; print(SCHEMA_VERSION)"` | `4` (matches planning) |
| `.venv/bin/python -c "from llm_wiki import config, db, scaffold, inbox"` | Import OK; all Phase-1 modules import cleanly |

### Pytest availability note

The shell-level `pytest` and `.venv/bin/pytest` entrypoints are unusable here
because `.venv/bin/pytest` has a stale shebang pointing at
`/home/eunjae/project/llm-wiki/.venv/bin/python3` (singular `project/`) instead
of `/home/eunjae/projects/llm-wiki/...`. This is a pre-existing infrastructure
issue and is unrelated to Phase 1 build work. Calling pytest via
`.venv/bin/python -m pytest` works correctly and was used for all runs above.

## Validation summary

- **Phase 1 deliverables are correct and complete.**
  - Schema v4 is idempotent and additive (does not touch existing
    `sources` / `ingest_runs` / `ingest_logs` / `ingest_jobs` / etc.).
  - `InboxState` / `InboxInputType` enums, `InboxItem` / `InboxEvent`
    dataclasses, and CRUD / event helpers are in place.
  - `WikiPaths` exposes `inbox`, `inbox_files`, `inbox_markdown`,
    `inbox_text`, `inbox_failed`, `inbox_review`, and a `raw_archive`
    alias for Raw archive semantics.
  - Ja layout (`00. Inbox/_Review`) keeps `WikiPaths.non_categories`
    pointing at `Inbox/_Review`, so existing `non_categories`-based tests
    continue to work.
  - `scaffold()` creates the Inbox dirs but never `_Processing`.
- **No regression** in the previously-passing Phase 1, Phase 3, parsers,
  relinking, or Korean prompt tests (20/20 pass with the new schema).
- All Phase 1 tests are deterministic, no network, no real model, no
  long-running server started.

## Scope note (not a Phase 1 blocker)

The implementation summary from the build primary listed only Phase 1 file
changes, but the worktree contains substantial **out-of-scope** modifications
that belong to Phase 2 (and one unrelated change). These are NOT Phase 1
deliverables and are tracked separately:

| File (out of Phase 1) | Lines | Phase |
| --------------------- | ----- | ----- |
| `src/llm_wiki/ingest_llm.py` | +925 / -165 | Phase 2 — 2-pass JSON page generation, validation, retry, staged lint gate |
| `src/llm_wiki/prompts.py` | +235 / 0 | Phase 2 — NEW_ENTITY/CONCEPT/MERGE JSON page templates |
| `src/llm_wiki/llm.py` | +5 / 0 | Unrelated — OpenAI-compatible HTTP error body surfacing |
| `tests/test_two_pass_generation.py` (new) | +1128 | Phase 2 — STAB-002/003 regression tests |
| `tests/test_staged_lint_gate.py` (new) | +340 | Phase 2 — STAB-001 staged lint gate test |
| `tests/test_phase2_candidates_schema.py` | +224 / 0 | Phase 2 — fake-client updates, malformed-wikilink fix test |

These changes were driven by the separate
`.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`
(STAB-001/002/003), and partial evidence already lives at
`.code-planner/03-build/evidence/2-pass-generation-fix-evidence.md`.

**Status of those out-of-scope tests when run today**:

| Test module | Pass | Fail | Note |
| ----------- | ---- | ---- | ---- |
| `tests/test_two_pass_generation.py` | 0 | 6 | All 6 fail with `AttributeError: '_*Client' object has no attribute 'provider'` — the new `ingest_source()` flow dereferences `client.provider` but fake clients do not set it |
| `tests/test_staged_lint_gate.py` | 0 | 1 | Same root cause (`AttributeError`) |
| `tests/test_phase2_candidates_schema.py` | 12 | 5 | 4 unrelated regressions (low-confidence entity/concept, candidate-only routing, review-candidates not written) plus the new `test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks` |

This is a **Phase 2 (and a Phase 2 stability fix) issue, not a Phase 1
issue**. Per the brief, Phase 1 WU-004 only validates the Phase 1
deliverables; the out-of-scope failures are recorded here as
`remaining risks` and should be addressed under the existing
`2-pass-generation-fix-request.md` workstream.

## Process / port cleanup

- This validation run started no dev server, no watcher, no port listener.
- A pre-existing `uvicorn` instance is running on port 8000 (PID 8343,
  parent PID 8326), unrelated to this WU and started well before this
  validation; it is left untouched per the destructive / cleanup policy.
- No background processes were spawned by the validator.

## Evidence artifacts

- This file: `.code-planner/03-build/evidence/phase-1-build-evidence.md`
- Cross-reference (separate WU / fix request, NOT Phase 1):
  `.code-planner/03-build/evidence/2-pass-generation-fix-evidence.md`

## Remaining risks

1. **Scope creep uncommitted in worktree.** Phase 2 / STAB-001/002/003
   changes are present in the working tree but unstaged. The Phase 1
   commit (`feat: add inbox domain model`) should land cleanly only on
   the Phase 1 files (`db.py`, `config.py`, `scaffold.py`, `inbox.py`,
   `tests/test_inbox_domain.py`). The build primary should decide
   whether to land Phase 1 separately and the STAB fixes in a follow-up
   commit, or amend the implementation summary to disclose the full set
   of changes.
2. **Out-of-scope tests are failing today.** Phase 2 stability tests
   (`test_two_pass_generation.py`, `test_staged_lint_gate.py`, parts of
   `test_phase2_candidates_schema.py`) fail because the fake LLM clients
   they use do not declare `client.provider`, which the modified
   `ingest_source()` now requires. This blocks a clean `/check phase-1`
   on a per-test-level run of the whole suite, but **does not** block
   Phase 1 itself. The fix likely belongs to the existing
   `2-pass-generation-fix-request.md` workstream (either add `provider`
   attributes to the fakes or make `client.provider` optional /
   safely-defaulted).
3. **Pytest shim shebang.** The `.venv/bin/pytest` shim has a stale
   absolute path; must be re-installed or invoked via
   `python -m pytest` from inside the venv. Pre-existing infrastructure
   issue; unrelated to build.

## Validation result

- **Phase 1 validation**: PASS for the Phase 1 deliverables.
  - All 4 Phase 1 inbox domain tests pass.
  - All 20 in-scope tests pass with no regression.
  - Schema is idempotent and additive.
  - P0 guardrails (idempotency, layout compatibility, no `_Processing`
    folder, enum match, migration repeat-safe) are all satisfied.

- **Out-of-scope (Phase 2 / STAB)**: partial — 11 of those tests fail
  today (see "Scope note"). This is tracked under the
  `2-pass-generation-fix-request.md` fix request and is not a Phase 1
  concern, but it does mean a blanket `pytest tests/` run will be red
  until that fix request is closed.

## Ready for /check

- **Phase 1 ready**: yes — Phase 1 deliverables (DB schema v4, path
  semantics, inbox helpers, scaffold, dedicated tests) are correct and
  satisfy all six Phase 1 validation-plan items.
- **Full-suite ready**: no — out-of-scope Phase 2 / STAB tests fail
  today and need to be addressed under their own workstream before a
  clean full-tree pytest pass is possible.

If `/check phase-1` is scoped strictly to Phase 1 deliverables (recommended
per the brief), this evidence supports passing the gate. If `/check` runs
the entire `tests/` suite, it will be red and the failure must be
acknowledged as belonging to the STAB fix request, not Phase 1.