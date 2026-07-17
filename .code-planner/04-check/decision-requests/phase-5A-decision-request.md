# Phase 5A Decision Record — Commit sequencing and Phase 5B alignment

- Phase: phase-5A — Inbox-to-Job dispatch mapping
- Working directory: project root
- Branch: feature/upgrade-plan-implementation (HEAD `865c5b1`)
- Date: 2026-07-16
- Status: **resolved** on 2026-07-16

## Summary

Phase 5A implementation is technically complete and correctly scoped:

- `inbox.materialize_source_for_inbox_item(...)` domain helper is implemented.
- `/ingest/start` accepts `inbox_item_id` (primary) and `source_id` (legacy).
- `/ingest/scan` no longer registers into the legacy `sources` queue; it imports Raw
  Sources into Inbox pending via `inbox.register_markdown_file` / `register_document_file`.
- `sources` rows are now materialized at job-start time, not at upload/scan time.
- `inbox_items.source_id` is persisted and reused.
- `jobs.enqueue(source_id)` / `ingest_llm.ingest_source(source_id)` are reused
  without modification (no diff in `jobs.py` or `ingest_llm.py`).

Verification:

- `tests/test_inbox_to_job_mapping.py` (3 tests): PASS.
- `tests/test_inbox_domain.py` (4 tests): PASS.
- `tests/test_inbox_registration.py` (16 tests): PASS.
- `tests/test_phase4_review_failed_workbench.py` (4 tests): PASS.
- `py_compile`: exit 0.
- `git diff --check`: exit 0.

Check subagent verdicts:

- `check-change-scope`: PASS (Phase 5A deliverables complete, files in scope).
- `check-code-stability`: pass-with-notes (2 hardening notes, no blockers).
- `check-user-test`: user functional test NOT REQUIRED; deferred to Phase 5B per
  planning ("UX/user testing은 Phase 5A 통과 전 금지").
- `check-git-final`: not-ready (check report missing — being drafted; plus stacked Phase 4).

Why this was a **decision request** and not a normal fix request:

- The implementation is correct. No Phase 5A code change can resolve the blockers below
  without expanding Phase 5A scope into Phase 5B territory.
- Both blockers require a planning/sequencing decision the user must make.

## Original blockers requiring user decision

### Blocker 1 — `tests/test_web_navigation.py` 2 failures (Phase 5B alignment gap)

**Resolution:** resolved by the user accepting the recommended path on 2026-07-16.
The two tests were updated in `tests/test_web_navigation.py` to assert the
approved Phase 5A Inbox-first API contract while explicitly documenting that
per-row Inbox rendering on `/ingest` remains a Phase 5B template responsibility.

Post-resolution verification:

```text
.venv/bin/python -m pytest tests/test_web_navigation.py -v
8 passed, 1 warning

.venv/bin/python -m pytest tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_inbox_domain.py tests/test_inbox_registration.py tests/test_phase4_review_failed_workbench.py -v
35 passed, 1 warning
```

**Concrete evidence:**

```text
$ .venv/bin/python -m pytest tests/test_web_navigation.py -v
FAILED tests/test_web_navigation.py::test_ingest_scan_registers_synced_raw_sources
       AssertionError: 'mobile-synced.md' not in <Response [200 OK]>.text
FAILED tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions
       AssertionError: '작업으로 보내기' not in <Response [200 OK]>.text
6 passed, 2 failed
```

**Root cause:**

Phase 5A intentionally changed `/ingest/upload` and `/ingest/scan` to register
Inbox items (`inbox_items` rows) instead of legacy `sources` rows. The legacy
`src/llm_wiki/webapp/templates/ingest.html` still iterates `pending` as
`sources` rows:

```html
{% for src in pending %}
  ...
  <button class="..." data-action="start-job" data-source-id="{{ src.id }}">
    작업으로 보내기
  </button>
{% endfor %}
```

So when a user runs `/ingest/scan` followed by `GET /ingest`, the new Inbox
pending items are *not* rendered. This is what the failing tests assert.

**Why this is not fixable inside Phase 5A's scope:**

The fix is to update `templates/ingest.html` to iterate `inbox_items` (with the
right workflow: per-item "start job", batch actions, etc.), which is the
explicit deliverable of Phase 5B:

```text
.code-planner/02-planning/phases/phase-5-ui-cli-integration.md:
- /ingest screen existing UX extension.
- /inbox filters/tabs and actions.
- /jobs inbox item display.
```

**Why this is a decision, not a fix:**

There are at least three reasonable resolutions; each has scope and commit-policy
implications only the user can resolve:

- (A) Hold Phase 5A approval and require Phase 5B to be built and committed first
  (so the template is aligned before Phase 5A's commit lands). Phase 5A and 5B
  become a single combined checkpoint.
- (B) Keep Phase 5A and Phase 5B as separate checkpoints. Update
  `tests/test_web_navigation.py` in this phase to assert the new Inbox-first
  semantic (the template rendering itself is updated in Phase 5B's commit).
- (C) Approve Phase 5A as `approved_with_notes` and commit, document the 2
  failing tests as known-issues with an explicit Phase 5B follow-up. This
  violates the "Do not commit when tests fail" rule unless the user explicitly
  approves the override.

### Blocker 2 — Stacked uncommitted Phase 4 work

**Resolution:** resolved at the decision level by the user accepting the
recommended sequencing on 2026-07-16:

- Commit sequencing = **Decision 2(A)**
- Phase 4 is treated as approved for commit sequencing purposes on the basis
  that user-facing functional verification is intentionally deferred to the
  later Phase 5B UI alignment gate.
- Phase 5A remains a separate checkpoint on top of the Phase 4 commit.

This does **not** mean a commit was made here. It means Check no longer blocks
Phase 5A on sequencing ambiguity. Actual git commits still require an explicit
user request.

**Concrete evidence:**

```text
$ git status --short
 M src/llm_wiki/inbox.py
 M src/llm_wiki/webapp/routes/inbox.py
 M src/llm_wiki/webapp/routes/ingest.py
 M src/llm_wiki/webapp/templates/inbox.html
 M tests/test_inbox_registration.py
?? .code-planner/
?? .prv/
?? tests/test_inbox_to_job_mapping.py
?? tests/test_phase4_review_failed_workbench.py

$ git diff --stat
 src/llm_wiki/inbox.py                    | 262 +++      (Phase 4 same-path guard + Phase 5A materialization)
 src/llm_wiki/webapp/routes/inbox.py      | 586 ++       (Phase 4 workbench; not in Phase 5A scope)
 src/llm_wiki/webapp/templates/inbox.html | 696 ++       (Phase 4 workbench UI; not in Phase 5A scope)
 src/llm_wiki/webapp/routes/ingest.py     | 107 ++       (Phase 5A scan/start rewrites)
 tests/test_inbox_registration.py         |  36 ++       (Phase 4 STAB-001 regression)
```

**Root cause:**

- Phase 4 was completed on 2026-07-16 with a check report that explicitly returned
  `changes_requested (gating on user functional test confirmation)` rather than
  approving and committing. The Phase 4 work has been awaiting user functional test
  approval since then.
- Phase 5A was implemented on top of the uncommitted Phase 4 tree, so the worktree
  currently carries both phases' diffs interleaved. The intended Phase 5A commit
  message (`feat: connect inbox items to ingest jobs`) cannot be cleanly isolated
  until the Phase 4 tree is finalized.
- `src/llm_wiki/inbox.py` in particular has +262 lines that mix the Phase 4
  `_safe_copy_or_move` same-path guard (`src/llm_wiki/inbox.py` ~line 591-594)
  with the Phase 5A `materialize_source_for_inbox_item` helper
  (`src/llm_wiki/inbox.py` ~line 579-747), so a "Phase 5A only" selective stage
  is non-trivial.

**Why this is not fixable inside Phase 5A's scope:**

Phase 4's commit gate is the user's functional test approval (per its check
report). Until Phase 4 is committed (or otherwise removed from the worktree),
Phase 5A cannot be cleanly committed without bundling Phase 4 changes.

**Why this is a decision, not a fix:**

- (A) Commit Phase 4 first (after the user explicitly approves Phase 4's commit
  on the basis of having later user-test coverage from Phase 5B), then commit
  Phase 5A on top. This requires the user to retroactively approve Phase 4's
  commit even though no formal user-test has occurred.
- (B) Stash Phase 4 changes, rebuild the minimal Phase 5A diff in isolation,
  commit Phase 5A, then unstash Phase 4 and commit it separately. Requires
  careful surgical editing of `inbox.py`, `tests/test_inbox_registration.py`,
  etc.
- (C) Commit Phase 4 and Phase 5A together as a single combined checkpoint.
  This loses the Phase 4 ↔ Phase 5A split that planning documented.
- (D) Revert Phase 4 from the worktree and rebuild it cleanly after Phase 5A.
  This loses the existing Phase 4 work that has been reviewed and validated.

## Optional informational notes (NOT blockers, recorded for housekeeping)

These are recorded but do not require user action. They can be addressed in
Phase 5A's commit or deferred to Phase 6.

- **STAB-001** (`build-backend-script-dev`): `parsers.ParserError` is not caught
  by `/ingest/start`. The route catches `ValueError` (→ 404) and `FileNotFoundError`
  (→ 400) but `parsers.ParserError` extends `Exception` so a corrupted/unreadable
  Inbox file surfaces as a 500. Suggested fix: broaden the handler to map
  `ParserError` → 400 with "file not parseable: …". Pure graceful-degradation
  hardening; not a regression.
- **STAB-002** (`build-core-dev`): In `materialize_source_for_inbox_item`, when
  `item.source_id` is set but the linked source row's `relpath` no longer
  matches, the previously-linked source row is silently orphaned. Suggested fix:
  append a `source_relink` audit event (or include `previous_source_id` in the
  `source_materialized_reused` data) for traceability.

These are recorded in the issue list and may be addressed separately.

## User decisions taken

### Decision 1 — Test failures (`tests/test_web_navigation.py`)

- [x] **(B)** Keep Phase 5A and Phase 5B as separate checkpoints. Update
  `tests/test_web_navigation.py` to assert the new Inbox-first semantic in
  Phase 5A's PR. Phase 5B re-aligns the assertions when the template update
  lands.

### Decision 2 — Commit sequencing (stacked Phase 4)

- [x] **(A)** Retroactively approve Phase 4 commit on the basis of later user-test
  coverage from Phase 5B, then commit Phase 5A on top.

### Decision 3 — Optional informational notes

- [x] **(B)** Defer STAB-001 and STAB-002 to a Phase 6 polish pass.

## Chosen path summary

- Decision 1 = **(B)** update the 2 `tests/test_web_navigation.py` tests to
  match Phase 5A's Inbox-first semantic in this PR; Phase 5B re-aligns them.
- Decision 2 = **(A)** retroactively approve Phase 4 commit (because user-test
  was deferred by planning until Phase 5A passes, and Phase 5A's user-test is
  further deferred to Phase 5B's UI alignment), then commit Phase 5A on top.
- Decision 3 = **(B)** defer hardening to Phase 6.

This combination produces:

- Phase 4 commit `feat: add inbox review workbench`
- Phase 5A commit `feat: connect inbox items to ingest jobs`
- Phase 5B commit `feat: integrate inbox flow in ui and cli` (after this
  checkpoint can run user functional tests on Phase 4 + Phase 5A + Phase 5B).

## Hard rules

- No source code may be edited by Check.
- No commit was made as part of this decision record update.
- User functional test is NOT required for Phase 5A per planning; it is
  deferred to Phase 5B.
- The former `tests/test_web_navigation.py` failures were resolved by test
  updates that align expectations with approved Phase 5A semantics.

## Evidence artifacts referenced

- Build evidence: `.code-planner/03-build/evidence/phase-5A-build-evidence.md` (311 lines)
- Build handoff/brief: `.code-planner/03-build/phases/phase-5A-execution-brief.md`
- Planning: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- Phase 4 check report: `.code-planner/04-check/phase-4-check-report.md`
- Previous fix request: `.code-planner/04-check/fix-requests/phase-4-fix-request.md`

## Related files

- `.code-planner/04-check/issue-list.md`
- `.code-planner/04-check/phase-5A-check-report.md` (draft, marked `blocked`)
