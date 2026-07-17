# Phase 1 Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-1-inbox-domain.md`
- `.code-planner/02-planning/features/feature-inbox-domain.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`

## Phase goal

Inbox-first ingest의 공통 DB 상태 모델과 path semantics를 구현한다. Phase 1은 실제 파일 이동, Web UI 변경, chunked extraction 구현을 포함하지 않는다.

## Work units

### WU-001. Existing code discovery and duplicate-risk scan

- Purpose: 기존 DB schema, migration pattern, path config, tests, jobs/source relationship을 파악하고 중복 구현 위험을 줄인다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `src/llm_wiki/config.py`, `src/llm_wiki/db.py`, `src/llm_wiki/jobs.py`, `src/llm_wiki/ingest_raw.py`, tests.
- Completion criteria: target files, existing patterns, migration/test commands, duplicate risks summarized.
- Verification: N/A read-only.

### WU-002. Inbox domain schema and helpers

- Purpose: idempotent DB migration, inbox state enum/constants, inbox event helper, optional candidate table skeleton을 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/db.py`, possibly new domain helper under `src/llm_wiki/` if existing patterns support it, focused tests.
- Completion criteria: existing sources/jobs/runs preserved; state enum matches planning; migration repeat-safe.
- Verification: targeted pytest for DB migration/domain helpers.

### WU-003. Path semantics and layout compatibility

- Purpose: Inbox root, `_Failed`, `_Review`, Raw archive path semantics를 명확화하고 `processing`이 physical folder가 아님을 보장한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/config.py`, related tests.
- Completion criteria: default and Ja layout compatibility; no `_Processing` folder requirement.
- Verification: targeted config/path tests.

### WU-004. Phase 1 validation and evidence readiness

- Purpose: Phase 1 validation plan에 맞춰 tests/commands를 실행하고 evidence 초안을 정리한다.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-1-build-evidence.md`, tests if needed.
- Completion criteria: command output, validation result, risks, ready-for-check flag documented.
- Verification: real validation commands executed after implementation.

## Out of scope

- Web UI 화면 변경.
- 실제 Inbox 등록/파일 이동 flow.
- Failed/Review action 구현.
- Chunked extraction implementation.
- qmd/Obsidian reset 기능.

## Validation commands

- `python -m pytest tests/test_phase1_* tests/test_phase2_* tests/test_phase3_* tests/test_phase4_*`
- Additional targeted tests discovered by WU-001.
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-1`: `feat: add inbox domain model`
- Do not commit until validation/evidence pass and `/check phase-1` gate is ready.

## Risks

- Existing 2-pass generation source changes may already be present in worktree.
- DB migration must not damage existing sources/jobs/runs.
- `non_categories` and Ja layout tests may encode existing Inbox assumptions.
- Overbuilding Phase 2 movement behavior in Phase 1 would exceed scope.
