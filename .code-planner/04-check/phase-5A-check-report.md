# Phase 5A Check Report

- Phase: phase-5A — Inbox-to-Job dispatch mapping
- Working directory: project root
- Branch: feature/upgrade-plan-implementation (HEAD `865c5b1`)
- Check date: 2026-07-16
- Gate result: **`approved_with_notes`**
- Commit hash: not committed (blocked)
- Commit message: pending user decision

## Source artifacts

- Build evidence: `.code-planner/03-build/evidence/phase-5A-build-evidence.md` (311 lines)
- Build handoff brief: `.code-planner/03-build/phases/phase-5A-execution-brief.md`
- Phase 5A planning: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md` (Phase 5A section)
- Phase 5A feature spec: `.code-planner/02-planning/features/feature-ui-cli-integration.md`
- Phase 5A validation plan: `.code-planner/02-planning/validation/01-validation-plan.md`
- Decision request: `.code-planner/04-check/decision-requests/phase-5A-decision-request.md`
- Issue list: `.code-planner/04-check/issue-list.md` (current)
- Phase 4 check report: `.code-planner/04-check/phase-4-check-report.md` (predecessor, reference)

## Changed files (git diff target)

Tracked modifications (`git diff --stat`):

```text
 src/llm_wiki/inbox.py                    | 262 ++++++++++++         (Phase 5A + stacked Phase 4)
 src/llm_wiki/webapp/routes/inbox.py      | 586 ++++++++++++++++++++++++--  (Phase 4 stacked only)
 src/llm_wiki/webapp/routes/ingest.py     | 107 +++--                 (Phase 5A only)
 src/llm_wiki/webapp/templates/inbox.html | 696 ++++++++++++++++++++++++++-----  (Phase 4 stacked only)
 tests/test_inbox_registration.py         |  36 ++                  (Phase 4 stacked only)
 tests/test_web_navigation.py             |  60 ++-                 (Phase 5A semantic-alignment test update)
 6 files changed, 1584 insertions(+), 163 deletions(-)
```

Untracked (Phase 5A scope):

- `tests/test_inbox_to_job_mapping.py` (new, 3 focused tests)

Untracked (Phase 4 stacked):

- `tests/test_phase4_review_failed_workbench.py` (new, 4 tests)

Untracked planning/review artifacts (not part of code change scope):

- `.code-planner/` — planning, evidence, check artifacts
- `.prv/` — PRV review session outputs

Phase 5A files explicitly NOT modified (verified by empty `git diff`):

- `src/llm_wiki/ingest_raw.py` — reused via `iter_addable_files`
- `src/llm_wiki/jobs.py` — reused via `jobs_module.get_manager(paths).enqueue(source_id)`
- `src/llm_wiki/ingest_llm.py` — reused via `ingest_source(source_id)`
- `src/llm_wiki/webapp/templates/ingest.html` — Phase 5B owner

## Affected flow

| Layer | Files | Change | Reference |
| --- | --- | --- | --- |
| Domain | `src/llm_wiki/inbox.py` | Added `InboxSourceMaterializationResult`, `_update_inbox_item_source_link`, `_refresh_existing_source_row`, `materialize_source_for_inbox_item` | inbox.py:579-747, 165-211 |
| Web route | `src/llm_wiki/webapp/routes/ingest.py` | `/ingest/scan` delegates to `inbox.register_markdown_file` / `register_document_file`; `/ingest/start` accepts `inbox_item_id` (primary) and `source_id` (legacy) | ingest.py:44-51, 128-188, 192-232 |
| Test (new) | `tests/test_inbox_to_job_mapping.py` | 3 focused tests covering all three Phase 5A validation items | full file |
| Test (updated) | `tests/test_web_navigation.py` | 2 Inbox-first semantic-alignment assertions for `/ingest/scan` and `/ingest/upload`; keeps `/ingest` HTML row rendering in Phase 5B scope | lines 110-164, 197-242 |
| Workbench (Phase 4 stacked) | `src/llm_wiki/webapp/routes/inbox.py`, `src/llm_wiki/webapp/templates/inbox.html` | Move/hold/retry/reprocess contracts (out of Phase 5A scope; documented for context) | Phase 4 evidence |

## Required check results

| Check | Result | Source |
| --- | --- | --- |
| 1. 변경 범위 검사 | passed (Phase 5A-only logic stays in scope) | check-change-scope verdict |
| 2. 영향 흐름 검사 | passed | check-change-scope verdict; all references coherent |
| 3. 기능 완성도 검사 | passed | check-change-scope verdict; Phase 5A acceptance criteria satisfied |
| 4. 안정성 검사 | pass-with-notes (STAB-001, STAB-002 informational; no blockers) | check-code-stability verdict |
| 5. 유지보수성 검사 | passed | check-code-stability verdict (MAINT-001/002) |
| 6. 보안/설정 검사 | passed | check-code-stability verdict (SEC-001) |
| 7. 검증 증거 검사 | passed (build evidence thorough) | build evidence file |

Notes affecting commit sequencing:

- `tests/test_web_navigation.py` Phase 5A semantic mismatch is resolved; suite now passes 8/8.
- Stacked Phase 4 work remains in the same worktree, but the user accepted the recommended sequencing: commit Phase 4 first, then Phase 5A.

## Convention result

- New `materialize_source_for_inbox_item(...)` follows the existing inbox domain
  helper shape (`move_to_failed`, `move_to_review`, `move_to_pending`,
  `register_markdown_file`, `register_document_file`).
- `InboxSourceMaterializationResult` is a `@dataclass(frozen=True)` matching the
  sibling `InboxRegistrationResult` / `InboxMoveResult` pattern.
- The new route code uses `request.app.state.wiki_paths`, `db.connect(...)`, and
  the `inbox_domain.move_to_*` / `register_*` patterns.
- Tests follow the existing `scaffold(tmp_path) + create_app(paths) + TestClient` pattern
  and add a small `_FakeManager` to exercise the route without spawning a worker.
- Template and JS files for `/ingest` are intentionally left to Phase 5B (the
  end-of-evidence "explicit non-claim" reinforces this).

## Code stability result

- Focused pytest for Phase 5A + Phase 1/2 inbox regression + Phase 4 workbench
  + web navigation semantic alignment (35 tests total): all green.
  - 3 new tests in `tests/test_inbox_to_job_mapping.py`.
  - 4 tests in `tests/test_inbox_domain.py`.
  - 16 tests in `tests/test_inbox_registration.py`.
  - 4 tests in `tests/test_phase4_review_failed_workbench.py`.
  - 8 tests in `tests/test_web_navigation.py`.
- `py_compile`: exit 0 on changed source files.
- `git diff --check`: exit 0.
- No secrets, env files, hardcoded hosts, or Tailscale IPs introduced.
- `ss -ltnp` and `ps -ef` show only pre-existing listeners; no Phase 5A process
  or port was started; no cleanup action required.

## Implementation completeness

Phase 5A acceptance criteria from `feature-ui-cli-integration.md` (Phase 5A section):

- [x] `inbox_item_id → source_id → ingest_job` mapping.
- [x] Materialize source from inbox_item (create or reuse sources row, persist
      `inbox_items.source_id`, audit `source_materialized` / `source_materialized_reused`
      / `source_materialization_hash_conflict` event).
- [x] `/ingest/start` accepts `inbox_item_id` (primary); preserves legacy
      `source_id` flow.
- [x] `/ingest/scan` no longer registers into the `sources` queue; imports
      Raw Sources into Inbox pending via `register_markdown_file` /
      `register_document_file`.
- [x] Reuses `jobs.enqueue(source_id)` and `ingest_llm.ingest_source(source_id)`
      without modification.

Explicit non-claim:

- `/ingest` HTML template is **not** modified. Phase 5B's deliverable is the
  `/ingest` UI alignment with the approved Ingest mockup.

## User functional test required

- Required: no (per planning "UX/user testing은 Phase 5A 통과 전 금지" and
  `check-user-test` verdict).
- Deferred to Phase 5B, which completes the UI alignment needed for a real
  end-to-end visual test (per the carry-over pattern from Phase 4).
- Approval state: not requested for Phase 5A.

## Git final verification result

- `git status --short`: Phase 5A + Phase 4 stacked under one worktree; see
  truncated output above.
- `git diff --name-only`: 6 tracked files.
- `git diff --check`: exit 0.
- `git diff --stat`: 1584 insertions / 163 deletions across 6 tracked files.
- No `.env`, secrets, cache, build outputs, or unrelated files in the diff.
- No new background process, watcher, or port listener introduced.

## Decision

- Result: **`approved_with_notes`**
- Reason: source-side Phase 5A deliverable is complete and validated; the former
  `tests/test_web_navigation.py` failures were resolved by aligning test
  expectations with approved Phase 5A Inbox-first semantics, and the user
  accepted the recommended sequencing that commits Phase 4 first and Phase 5A
  second.
- Remaining note: actual git commit has not been requested or performed, and the
  worktree still contains stacked Phase 4 + Phase 5A changes that must be staged
  in the chosen order.

## Commit plan

After the user requests commit execution, the intended Phase 5A commit is:

```text
feat: connect inbox items to ingest jobs

Phase: phase-5A
Check: approved | approved_with_notes
Evidence: .code-planner/04-check/phase-5A-check-report.md
```

Under the chosen path (Decision 1 = B, Decision 2 = A, Decision 3 = B), Phase 5A
staging should include:

- `src/llm_wiki/webapp/routes/ingest.py`
- `tests/test_inbox_to_job_mapping.py`
- `tests/test_web_navigation.py` (test-only edit aligning expectations with
  Phase 5A's Inbox-first semantic)
- `src/llm_wiki/inbox.py` (Phase 5A additions interleaved with Phase 4
  same-path guard)
- Phase 4 commit happens first with: `src/llm_wiki/webapp/routes/inbox.py`,
  `src/llm_wiki/webapp/templates/inbox.html`, `tests/test_inbox_registration.py`,
  `tests/test_phase4_review_failed_workbench.py`, and the shared `src/llm_wiki/inbox.py`
  changes required by Phase 4.

## Evidence

- `.code-planner/03-build/evidence/phase-5A-build-evidence.md` (311 lines)
- `.code-planner/03-build/evidence/phase-4-build-evidence.md` (predecessor)
- `.code-planner/03-build/evidence/phase-4-fix-evidence.md` (Phase 4 fix evidence)
- `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md` (Phase 5A spec)
- `.code-planner/02-planning/features/feature-ui-cli-integration.md` (acceptance criteria)
- `.code-planner/02-planning/validation/01-validation-plan.md` (validation plan)
- `.code-planner/04-check/decision-requests/phase-5A-decision-request.md` (resolved)
- `.code-planner/04-check/issue-list.md`
- `.code-planner/04-check/phase-4-issue-list-archived.md` (Phase 4 historical issue list)
- `.code-planner/04-check/phase-4-check-report.md` (predecessor)
