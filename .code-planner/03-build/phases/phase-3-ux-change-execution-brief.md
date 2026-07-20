# Phase 3 UX Change Execution Brief

## Source planning docs

- `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`
- `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- `.code-planner/02-planning/review/phase-3-ui-consistency-review.md`
- `.code-planner/02-planning/handoff/build-handoff.md`
- `.code-planner/02-planning/validation/validation-plan.md`

## Phase goal

Phase 3 전체 재설계가 아니라 UX 변경 건만 반영한다.

1. Mobile `<768px`에서 상단 메뉴 가로 나열 제거 및 `☰` side drawer 적용
2. Mapping 화면에 기존 wiki match 선택/전환과 Add/Merge/Create/Confirm mapping CTA 명확화
3. PC/Mobile CTA 위치, 버튼 크기, Logout 임시 위치 계약 준수

## Work units

### WU-001. Existing UI discovery and target-file confirmation

- Purpose: 기존 Web UI 구조, 중복 위험, 테스트 영향을 확인한다.
- Assigned agent: `codebase-explorer`
- Expected files: none, read-only
- Completion criteria: 변경 대상 파일, 기존 nav/mapping/action/test 구조, 중복 위험 보고
- Verification: discovery report returned

### WU-002. Mobile side drawer and Mapping action UI implementation

- Purpose: UX change plan에 맞춰 템플릿/CSS/JS만 수정한다.
- Assigned agent: `build-ui-dev`
- Expected files:
  - `src/llm_wiki/web/templates/base.html`
  - `src/llm_wiki/web/templates/mapping.html`
  - `src/llm_wiki/web/templates/settings.html`
  - `src/llm_wiki/web/static/css/style.css`
  - `src/llm_wiki/web/static/js/app.js`
- Completion criteria:
  - Mobile top nav 가로 나열 제거
  - `☰` drawer + nested Mapping/Settings menu + active state
  - Logout top-level 제거, Settings/Auth 또는 drawer의 Auth/Logout 임시 접근 유지
  - Mapping existing wiki matches, Use/Switch, Add/Merge/Create/Edit/Reject/Confirm CTA
  - Add/Merge disabled 상태와 select wiki 안내
  - Mobile sticky CTA에 mapping action 포함
- Verification: targeted tests or static/template checks where possible

### WU-003. Contract tests and validation update

- Purpose: 변경된 UX 계약에 맞춰 기존 Phase 3 UI 테스트를 보정하고 검증한다.
- Assigned agent: `build-test-validation`
- Expected files:
  - `tests/test_web_phase3_approved_contracts.py`
  - `tests/test_web_phase3_fix.py`
  - 필요 시 추가/수정 테스트 파일
- Completion criteria:
  - Top nav에서 Logout 제외 계약 반영
  - Side drawer/nested menu/active state 테스트
  - Mapping existing wiki/action CTA 테스트
  - UX change plan 범위 밖 테스트/기능 변경 없음
- Verification:
  - `pytest tests/test_web_phase3_approved_contracts.py tests/test_web_phase3_fix.py`
  - 필요 시 관련 Phase 3 web tests subset

### WU-004. Integration validation and evidence

- Purpose: 서브에이전트 결과 통합, 실제 검증, evidence 작성
- Assigned agent: `build-test-validation`
- Expected files:
  - `.code-planner/03-build/evidence/phase-3-ux-change-build-evidence.md`
- Completion criteria:
  - git diff 범위 확인
  - `git diff --check` 통과
  - 관련 pytest 결과 기록
  - remaining risks 기록
- Verification:
  - `git status`
  - `git diff --stat`
  - `git diff --check`

## Out of scope

- Phase 3 전체 재설계
- 데이터 schema 변경
- LLM candidate 생성 로직 변경
- 신규 사용자/프로필 메뉴 구현
- 다중 사용자 권한
- 신규 프론트엔드 프레임워크/빌드 도구 도입
- 신규 API endpoint 추가

## Validation commands

```bash
pytest tests/test_web_phase3_approved_contracts.py tests/test_web_phase3_fix.py
pytest tests/test_web_phase3_stability.py tests/test_web_decide.py tests/test_web_setup_wiki.py
git diff --check
```

## Git checkpoint plan

- 이번 단계에서는 commit하지 않는다.
- 검증/evidence 작성 후 `/check phase-3`로 넘긴다.

## Risks

- 기존 테스트가 top-level Logout을 강하게 기대해 테스트 보정 필요
- `Add to selected wiki`와 `Merge into selected wiki`의 backend 의미가 동일할 수 있으므로 API/schema 변경 없이 metadata/action label 중심으로 제한
- Mobile sticky CTA와 기존 sticky action bar가 중복될 위험이 있어 기존 action bar 확장 우선
- Tablet `768–1023px`는 현재 계획상 desktop/mobile 중간이며, UI 깨짐 없이 동작하는지 검증 필요
