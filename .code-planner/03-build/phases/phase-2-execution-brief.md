# Phase 2 Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-2-inbox-registration-movement.md`
- `.code-planner/02-planning/features/feature-inbox-registration.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`

## Phase goal

사용자 입력 3유형을 Inbox item으로 등록하고, 처리 결과에 따라 Raw Sources archive / `Inbox/_Failed` / `Inbox/_Review`로 원본을 이동할 수 있는 backend foundation을 구현한다.

## Work units

### WU-001. Existing flow discovery and conflict scan

- Purpose: 기존 raw registration, CLI add, web upload/paste, source/job 처리 흐름과 현재 worktree의 2-pass/STAB 변경 충돌 위험을 파악한다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `src/llm_wiki/ingest_raw.py`, `src/llm_wiki/cli.py`, `src/llm_wiki/webapp/routes/ingest.py`, `src/llm_wiki/jobs.py`, `src/llm_wiki/ingest_llm.py`, tests.
- Completion criteria: target implementation files, reusable helpers, affected tests, scope-separation risks summarized.
- Verification: N/A read-only.

### WU-002. Inbox registration and movement backend helpers

- Purpose: document/markdown/pasted text를 Inbox 하위 convention에 등록하고, 상태 전이와 파일 이동 helper를 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/inbox.py`, `src/llm_wiki/ingest_raw.py` or new focused helper, targeted tests.
- Completion criteria: three input types create Inbox items; duplicate/hash/collision handling works; processing is DB state/lock only.
- Verification: targeted pytest for inbox registration/movement.

### WU-003. Failed/Review/archive routing helpers and diagnostics

- Purpose: success -> Raw archive, failure -> `_Failed` + report, review -> `_Review` movement primitives를 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/inbox.py` or focused helper, tests.
- Completion criteria: move failure evidence records source path, target path, DB state, retry capability; no source loss on move failure.
- Verification: targeted pytest covering success/failure/review and move failure.

### WU-004. CLI/Web registration integration minimum

- Purpose: 기존 CLI add 및 Web upload/paste가 Inbox 등록으로 연결될 수 있는 최소 integration을 구현한다. UI redesign은 Phase 5까지 보류한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli.py`, `src/llm_wiki/webapp/routes/ingest.py`, focused tests if existing patterns allow.
- Completion criteria: upload/paste/file-add path can create Inbox item without using Raw Sources as input point.
- Verification: targeted CLI/API tests or lower-level route helper tests.

### WU-005. Phase 2 validation and evidence readiness

- Purpose: Phase 2 validation plan에 맞춰 tests/commands를 실행하고 evidence를 작성한다.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-2-build-evidence.md`, tests if needed.
- Completion criteria: command output, validation result, scope notes, ready-for-check flag documented.
- Verification: real validation commands executed after implementation.

## Out of scope

- Review workbench detailed actions.
- Chunked extraction map-reduce.
- New UI design or template redesign.
- qmd/Obsidian reset feature.
- Existing 2-pass/STAB worktree changes except where direct conflicts must be noted.

## Validation commands

- `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py -v`
- Additional targeted tests discovered by WU-001.
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-2`: `feat: route inputs through inbox`
- Stage only Phase 2 files. Keep pre-existing 2-pass/STAB changes separate unless explicitly included by Phase 2 scope and validated.

## Risks

- Current worktree contains pre-existing 2-pass/STAB changes in `ingest_llm.py`, `prompts.py`, `llm.py`, and tests. These can make full-suite validation red and must be separated in evidence.
- Existing `ingest_raw.add_file()` copies into Raw Sources; Phase 2 must avoid Raw Sources as the new input point while preserving compatibility or migration path.
- Move operations must not lose source files on target collision or failure.
- Web/CLI integration may be larger than backend-only Phase 2; if template UX changes are required, defer them to Phase 5.
