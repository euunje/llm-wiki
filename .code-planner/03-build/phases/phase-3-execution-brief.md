# Phase 3 Execution Brief

## Source planning docs

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/mockups/README.md`
- `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`
- `.code-planner/02-planning/review/phase-3-ux-mockup-approval.md`
- `sketches/mapping-node-review-mockup/index.html`
- `sketches/mapping-node-review-mockup/screenshot.png`

## Phase goal

승인된 Mapping Node Review 목업에 맞춰 `/mapping` UI를 시각적으로 재설계한다. 범위는 좌측 노드 리스트 + 우측 문서 검토/편집 2-pane, 명시적 노드명 영역, Wiki Page 카드(Frontmatter/Content), 비주요 LLM 진단 섹션, dirty-save/confirm guard, 하단 3버튼 액션바를 구현·정리하는 데 한정한다.

## Work units

### WU-001. Existing mapping UI discovery and duplicate-risk scan
- Purpose: 기존 mapping template/JS/CSS/test 구조, legacy path, 재사용 가능 helper를 확인한다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only scan of `src/llm_wiki/web/templates/mapping.html`, `src/llm_wiki/web/static/js/app.js`, `src/llm_wiki/web/static/css/style.css`, `src/llm_wiki/web/app.py`, `tests/test_web_decide.py`, `tests/test_web_phase3_approved_contracts.py`, `tests/test_web_phase3_state_visibility.py`.
- Completion criteria: 현재 mapping UI symbol, duplicate-risk, backend 필요 여부가 brief/evidence에 기록된다.
- Verification: discovery result from `codebase-explorer`.

### WU-002. Mapping UI visual redesign implementation
- Purpose: 승인 mockup 기준으로 mapping template/JS/CSS를 재구성해 섹션 hierarchy, frontmatter grid, content editor, similar-node panel, sticky action bar를 개선한다.
- Assigned agent: `build-ui-dev`
- Expected files: `src/llm_wiki/web/templates/mapping.html`, `src/llm_wiki/web/static/js/app.js`, `src/llm_wiki/web/static/css/style.css`.
- Completion criteria: 보류 버튼이 primary UI에서 제거되고, 저장은 dirty일 때만 활성화되며, 확정은 dirty 상태에서 경고 후 submit되지 않고, Claim은 별도 secondary section으로 분리된다.
- Verification: focused pytest + JS syntax check + mockup/text landmark inspection.

### WU-003. Mapping draft/decision backend contract adjustment if required
- Purpose: UI 요구사항 충족에 필요한 최소 backend field/contract만 수정한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/web/app.py`, `tests/test_web_decide.py`.
- Completion criteria: draft 저장/재조회/확정 guard에 필요한 API contract가 실제 UI와 테스트에서 일치한다.
- Verification: focused pytest for `/api/mapping/draft` and `/api/review/suggestions/decide-node`.

### WU-004. Focused test updates and validation evidence
- Purpose: approved contracts/state visibility/decision tests를 redesign 범위에 맞게 갱신하고 실행 근거를 남긴다.
- Assigned agent: `build-test-validation`
- Expected files: `tests/test_web_decide.py`, `tests/test_web_phase3_approved_contracts.py`, `tests/test_web_phase3_state_visibility.py`, `.code-planner/03-build/evidence/phase-3-build-evidence.md`.
- Completion criteria: 지정 pytest와 `git diff --check` 결과가 evidence에 기록된다.
- Verification: `.venv/bin/python -m pytest -q tests/test_web_decide.py tests/test_web_phase3_approved_contracts.py tests/test_web_phase3_state_visibility.py`, `git diff --check`.

## Out of scope

- Inbox/Vault/Wiki/Settings/LLM pipeline/CLI 파일 수정.
- 승인 mockup 밖 정보구조 변경 또는 새로운 dependency 추가.
- live candidate 대상 실제 의사결정 실행.
- destructive git/database 명령.

## Validation commands

```text
node --check src/llm_wiki/web/static/js/app.js
.venv/bin/python -m pytest -q tests/test_web_decide.py tests/test_web_phase3_approved_contracts.py tests/test_web_phase3_state_visibility.py
git diff --check
git status --short
git diff --stat
```

## Git checkpoint plan

- Planned checkpoint label: `phase-3-mapping-ui-visual-redesign`.
- Do not commit unless explicitly requested and validation/evidence gates are clean.
- Hand off to `/check phase-3` after build validation.

## Risks

- Current `app.js` contains legacy mapping code path alongside the redesigned path; avoid breaking unrelated review pages while refactoring.
- Mapping decision API may already support draft persistence; backend edits must stay minimal and test-driven.
- Do not expose secrets or hardcode localhost/host URLs while updating client logic.
