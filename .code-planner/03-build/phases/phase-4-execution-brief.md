# Phase 4 Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-4-review-failed-workbench.md`
- `.code-planner/02-planning/features/feature-review-failed-workbench.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.html`
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`

## Phase goal

`Inbox/_Review`와 `Inbox/_Failed`를 사용자가 처리 가능한 Web workbench로 확장한다. 기존 `/inbox` 좌측 목록 + 우측 preview/control layout을 유지하고, Review 후보/Failed diagnostics/actions를 표시한다.

## Work units

### WU-001. Existing Review/Failed flow discovery

- Purpose: 기존 `/inbox`, relinker/promote, inbox domain helpers, failed diagnostic file format, tests를 탐색해 중복 구현과 scope creep을 막는다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `src/llm_wiki/webapp/routes/inbox.py`, `templates/inbox.html`, `src/llm_wiki/inbox.py`, `src/llm_wiki/relinker.py`, tests.
- Completion criteria: target files/functions, existing patterns, safe action model, tests summarized.
- Verification: N/A read-only.

### WU-002. Review/Failed backend actions and data contract

- Purpose: Review/Failed item list/detail/action APIs 또는 route helpers를 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/webapp/routes/inbox.py`, `src/llm_wiki/inbox.py` if small helper needed, focused tests.
- Completion criteria: Review/Failed items can be listed/inspected; Failed diagnostics can be read/deleted; Review hold/delete/tag/classify or create/merge actions have a minimal tested contract.
- Verification: targeted pytest.

### WU-003. Existing-UX workbench UI extension

- Purpose: 승인 목업 기준으로 기존 `/inbox` template를 확장한다.
- Assigned agent: `build-ui-dev`
- Expected files: `src/llm_wiki/webapp/templates/inbox.html`, static-free/minimal CSS if existing pattern requires.
- Completion criteria: Review/Failed filters, selected item detail, candidates/log preview, action controls match approved existing UX baseline.
- Verification: template/render tests or route snapshot assertions.

### WU-004. Phase 4 validation and evidence readiness

- Purpose: Phase 4 validation plan에 맞춰 tests/commands를 실행하고 evidence를 작성한다.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-4-build-evidence.md`.
- Completion criteria: command output, mockup alignment, remaining risks, ready-for-check flag documented.
- Verification: real validation commands executed after implementation.

## Out of scope

- New design system.
- Raw physical chunk split.
- Chunked extraction implementation.
- `/ingest` template redesign (Phase 5).
- Full Inbox item → source/job mapping beyond action hooks required for Review/Failed display.

## Validation commands

- `.venv/bin/python -m pytest tests/test_inbox_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v`
- Existing relevant tests discovered by WU-001.
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-4`: `feat: add inbox review workbench`
- Stage only Phase 4 source/test files and related evidence/check report when explicitly requested.

## Risks

- Existing `/inbox` currently serves legacy `non_categories` review promotion; must preserve or migrate behavior safely.
- Review actions can become large; implement minimal tested action contract rather than full UX redesign.
- Failed diagnostic deletion must avoid deleting source files unless explicitly requested by action.
- Approved mockup requires similar candidates/tagging controls, but real similarity scoring may not exist yet; if unavailable, use existing metadata/reason fields and document limitation.
