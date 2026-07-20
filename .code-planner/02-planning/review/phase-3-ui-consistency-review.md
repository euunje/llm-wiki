# Phase 3 UI Consistency Review — 2026-07-19

## Trigger

사용자가 Phase 3 web-ui의 일치성 문제를 지적했다.

- 기본 지원: PC + Mobile
- 점검 대상: 상단 메인 메뉴, 서브메뉴 위치, 버튼 위치/사이즈

## Subagent result

- checkResult: `issues_found`
- 주요 문제:
  - top nav 항목이 mockup마다 다름
  - Mapping 구조가 3분할 / wizard / stepper로 분산됨
  - Settings submenu가 좌측 tab과 내부 task list로 혼재됨
  - 버튼 padding/font/color/variant가 mockup마다 다름
  - mobile breakpoint가 900/1000/1100/620 등으로 분산됨
  - 일부 phase/feature 문서는 모바일을 제외하지만 승인 문서는 responsive를 요구함

## User decisions

1. Phase 3 web UI는 통합한다.
2. Mobile Mapping에서도 핵심 결정 액션을 허용한다.
   - `Reject + Retry`
   - `Confirm`
3. Logout은 사용자 메뉴 dropdown에 배치한다.
   - 단, 사용자 메뉴는 아직 존재하지 않는다.
   - 따라서 Build는 top-level nav에 Logout을 추가하지 않는다.
   - 사용자 메뉴 구현 전에는 Settings > Auth에 임시 logout 액션을 둘 수 있다.
4. 모바일은 상단 메뉴 나열이 아니라 사이드 메뉴 버튼(☰)으로 세부 메뉴에 진입한다.

## Canonical UI direction

### PC

- Global top nav:
  - `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings`
- Logout:
  - future user menu dropdown
  - not a top-level nav item
- Submenu:
  - Settings: 좌측 submenu 우선 (`LLM / Prompt / Vault / Auth`)
  - Mapping: 상단 stepper + 좌측 candidate queue
  - Wiki/Vault: 좌측 list/tree + 우측 content
- Buttons:
  - primary CTA는 화면 우측 상단 또는 작업 panel 하단
  - destructive/retry는 primary와 색/위치가 구분되어야 함

### Mobile

- Global nav:
  - compact header + 좌측 사이드 메뉴 버튼(☰)
  - 상단에 메뉴 항목을 나열하지 않음
  - 사이드 drawer 안에서 top-level 항목과 세부 메뉴를 모두 탐색
- Submenu:
  - Mapping step, Settings section 같은 세부 메뉴는 사이드 drawer 안에 nested item으로 표시
  - 본문에는 현재 선택된 세부 화면만 단일 column으로 표시
- Mapping:
  - 단일 column stepper
  - `Reject + Retry`, `Confirm` 허용
  - 주요 CTA는 하단 sticky 영역
- Minimum touch target:
  - 44px 이상

## Design tokens

- Breakpoint:
  - desktop: `>= 1024px`
  - tablet: `768–1023px`
  - mobile: `< 768px`
- Button variants:
  - primary
  - secondary
  - destructive
  - warn
- Button size:
  - desktop: height 36–40px
  - mobile: height >= 44px

## Planning updates required

- `phases/phase-3-web-review-ui.md`: mobile 지원과 canonical mockup 기준 반영
- `features/feature-phase3-web-review-ui.md`: Mapping 구조와 button/nav 규칙 반영
- `mockups/phase-3-web-review-mockup.md`: legacy 충돌 해소 및 통합 구조 명시
- `mockups/phase-3-ui-integrated-mockup.html`: top nav, user menu placeholder, mobile CTA 기준 보강
- `validation/validation-plan.md`: PC/Mobile UI 일치성 required checks 추가

## Mockup remake — mobile side menu

- Date: 2026-07-19
- Updated file: `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Change:
  - 모바일 상단 메뉴 나열 제거
  - `☰` 사이드 메뉴 버튼 추가
  - drawer 안에 main menu + Mapping step + Settings section nested menu 표시
  - 모바일 Mapping은 drawer에서 step 진입 후 단일 column workspace + 하단 sticky CTA 사용
  - PC는 기존처럼 상단 global nav 유지

## Mapping action correction — existing wiki mapping

- Date: 2026-07-19
- Issue: 재작성 목업에서 기존 wiki와 매핑할 버튼 액션이 보이지 않았다.
- Correction:
  - Mapping 화면에 `Existing wiki matches` 영역 추가
  - `Use this wiki` / `Switch` 액션 추가
  - `Add to “RAG”`, `Merge into “RAG”`, `Create new “Agentic RAG”`, `Confirm mapping` CTA 추가
  - 기존 wiki 미선택 시 Add/Merge disabled + `select wiki` 안내 명시
  - Mobile sticky CTA에도 기존 wiki 매핑 액션을 포함하도록 문서화

## Build instruction plan

- UX change plan: `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`
- Scope: 전체 Phase 3 계획이 아니라 mobile side menu와 Mapping existing wiki action 변경 건만 지시

## PRV review

- URL: `http://127.0.0.1:44459/session/20260719T122950Z-297c09`
- Package: `.prv/opencode-review-package-1784464189782.json`
- Mode: local
- Status: pending user review

## Tailnet PRV review

- URL: `http://100.66.135.34:46695/session/20260719T123122Z-3a88b5`
- Package: `.prv/opencode-review-package-1784464281358.json`
- Mode: tailnet
- Status: stale/reopened

## Tailnet PRV rereview

- URL: `http://100.66.135.34:33123/session/20260719T124512Z-d6f972`
- Package: `.prv/opencode-review-package-1784465111589.json`
- Mode: tailnet
- Status: stale/replaced by side-menu mockup review

## Tailnet PRV side-menu mockup review

- URL: `http://100.66.135.34:39237/session/20260719T125220Z-2a80e5`
- Package: `.prv/opencode-review-package-1784465539529.json`
- Mode: tailnet
- Status: stale/replaced by mapping action correction review

## Tailnet PRV mapping action correction review

- URL: `http://100.66.135.34:36303/session/20260719T125745Z-43932b`
- Package: `.prv/opencode-review-package-1784465864816.json`
- Mode: tailnet
- Status: pending user review
