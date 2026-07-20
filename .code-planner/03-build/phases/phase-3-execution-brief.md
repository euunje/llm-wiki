# Phase 3 Execution Brief

## Source planning docs

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/phases/phase-3-web-review-ui.md`
- `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`
- `.code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md`
- `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`
- `.code-planner/02-planning/mockups/README.md`
- `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`
- `.code-planner/02-planning/review/phase-3-prv-feedback.md`

## Phase goal

Phase 3 Web UI를 승인된 UX 범위 안에서 상용화/안정화한다. 핵심 목표는 placeholder success, fake queue, UI-only action을 제거하고, Setup/Onboarding, API/UI contract, Inbox processing, Mapping decision effect, Settings test semantics, operational state visibility가 실제 DB/Vault/artifact/test evidence로 재현되게 만드는 것이다.

## Work units

### WU-001. Existing code discovery and duplicate-risk scan
- Purpose: 기존 FastAPI routes/templates/static/services/tests를 확인하고 Phase 3 정상 운영 gap을 분류한다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only scan of `src/llm_wiki/web/**`, `src/llm_wiki/schema/**`, `src/llm_wiki/pipeline/**`, `src/llm_wiki/jobs/**`, `tests/test_web_*.py`.
- Completion criteria: WU-01~WU-06의 구현/미구현 상태와 target files가 evidence에 기록된다.
- Verification: Discovery result from `codebase-explorer`.

### WU-002. Setup/Onboarding lifecycle and field contract
- Purpose: setup 미완료 사용자를 Onboarding으로 유도하고 완료 후 Dashboard/nav 상태를 실제 setup status로 제어한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/web/app.py`, `src/llm_wiki/web/templates/base.html`, `src/llm_wiki/web/static/js/app.js`, focused tests.
- Completion criteria: `/api/setup/status`가 `needs_onboarding` 등 checklist field를 반환하고, root/login flow 및 nav/drawer가 setup 상태와 일치한다.
- Verification: API snapshot/focused pytest.

### WU-003. Inbox processing lifecycle
- Purpose: Web upload/text/scan/process가 실제 Source/Job/Artifact 처리 경로로 이어지게 하며 placeholder queue를 제거한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/web/app.py`, `src/llm_wiki/pipeline/**`, `src/llm_wiki/jobs/**`, focused tests.
- Completion criteria: Markdown upload/process 후 job 상태가 실제 pipeline 결과로 갱신되고 success/failure artifact 및 retry evidence가 남는다.
- Verification: Markdown process focused pytest and artifact assertions.

### WU-004. Mapping decision effect
- Purpose: Mapping action이 단순 decision row가 아니라 preview_then_confirm 정책에 따라 DB/Vault/index 또는 queued 상태로 재조회 가능한 효과를 남기게 한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/web/app.py`, `src/llm_wiki/schema/review.py`, Vault/wiki helper modules if existing, focused tests.
- Completion criteria: Add/Merge/Create/Edit/Reject/Confirm action별 DB decision/effect row와 필요한 Vault Markdown/result 상태가 확인된다.
- Verification: focused pytest with DB row and Vault file assertions.

### WU-005. Settings test semantics and prompt usage
- Purpose: LLM connection/prompt test를 `passed | failed | blocked` 의미 있는 검증으로 만들고 failed/blocked confirm을 막는다.
- Assigned agent: `build-backend-script-dev`
- Expected files: `src/llm_wiki/web/app.py`, `src/llm_wiki/schema/prompts.py`, `src/llm_wiki/llm/**`, focused tests.
- Completion criteria: prompt test artifact에 validation type/status/reason/sample evidence가 남고 confirmed prompt id가 task run artifact/agent_run에 일관되게 기록된다.
- Verification: success/fail/blocked prompt test focused pytest.

### WU-006. Operational state visibility UI
- Purpose: Dashboard/Mapping/Search/Ask/Vault에서 setup missing, no data, processing, success, failure를 구분해 다음 행동을 안내한다.
- Assigned agent: `build-ui-dev`
- Expected files: `src/llm_wiki/web/templates/**`, `src/llm_wiki/web/static/js/app.js`, `src/llm_wiki/web/static/css/style.css`, focused tests.
- Completion criteria: silent fallback이 없고 주요 empty/error/success state가 별도 message와 next action을 가진다.
- Verification: template/API contract tests and JS syntax check.

### WU-007. Validation and build evidence
- Purpose: Phase 3 정상 운영 검증을 실행하고 evidence를 작성한다.
- Assigned agent: `build-test-validation`
- Expected files: `tests/test_web_phase3_normal_operation.py`, `.code-planner/03-build/evidence/phase-3-build-evidence.md`, `.code-planner/03-build/evidence/phase-3-normal-operation/`.
- Completion criteria: real command output, files changed, subagents, discovery, validation, remaining risks가 evidence에 기록된다.
- Verification: `py_compile`, `node --check`, focused pytest, `git diff --check`, `git status`, `git diff --stat`.

## Out of scope

- 승인 목업/Phase 3 문서 밖 UI 재설계.
- React/Vite/Next/Tailwind build pipeline 또는 승인되지 않은 dependency 추가.
- 다중 사용자 권한/협업 approval workflow.
- Web에서 Vault 전체 직접 편집기 구현.
- destructive command 또는 DB 강제 migration.
- 실제 secret/API key/host/Tailscale/localhost URL을 reusable code에 hardcode.

## Validation commands

```text
python -m py_compile src/llm_wiki/web/app.py src/llm_wiki/schema/prompts.py src/llm_wiki/schema/review.py
node --check src/llm_wiki/web/static/js/app.js
python -m pytest tests/test_web_phase3_normal_operation.py tests/test_web_phase3_approved_contracts.py tests/test_web_phase3_stability.py tests/test_web_settings.py tests/test_web_review.py
git diff --check
git status --short
git diff --stat
```

## Git checkpoint plan

- Planned checkpoint label: `phase-3-normal-operation-stabilization`.
- Do not commit unless explicitly requested and validation/evidence gates are clean.
- Hand off to `/check phase-3` after build validation.

## Risks

- Existing `api_inbox_process` is reported as placeholder queue and may require careful synchronous runner integration.
- Mapping decision effects need schema-compatible Vault/index behavior without broad architecture changes.
- Prompt test should avoid requiring real secret in automated tests; blocked/fail states must be explicit.
- `.env` exists locally with secrets per discovery; do not read, print, stage, or expose it.
