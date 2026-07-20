# Phase 3 — Web Review UI

## Purpose

단일 관리자 사용자가 PC와 Mobile Web에서 처리 현황을 보고 LLM 후보를 검토하며 병합/신규/retry/prompt 관리를 할 수 있게 한다.

## User-visible outcome

- 로그인 후 대시보드에서 자료 처리 현황과 시스템 상태를 본다.
- Mapping 화면에서 후보 queue, 3-step wizard, 오류/에러 tab을 통해 신규 개념 batch를 검토한다.
- 신규 개념을 병합/신규/수정/reject+retry 처리한다.
- 그래프 팝업에서 1-hop 관계와 wiki 내용을 확인한다.
- Web Settings에서 model/prompt를 설정하고 prompt test version을 confirmed version으로 승격한다.

## Related mockup

- Markdown mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.md`
- Canonical HTML mockup: `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Legacy HTML mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`은 더 이상 구현 기준이 아니며, 통합 mockup과 충돌할 경우 통합 mockup을 우선한다.
- PRV feedback: `.code-planner/02-planning/review/phase-3-prv-feedback.md`
- Approval status: approved

## Included features

- Onboarding/Login → Dashboard
- Global top navigation
  - PC: `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings`
  - Logout: top-level menu에 두지 않고 향후 사용자 메뉴 dropdown에 배치한다. 사용자 메뉴가 아직 없으면 임시로 Settings > Auth 안에만 둔다.
  - Mobile: 상단 메뉴 나열이 아니라 좌측 사이드 메뉴 버튼(☰)을 사용한다. drawer 안에서 top-level 항목과 세부 메뉴에 진입한다.
- Dashboard status cards
  - 자료 처리 현황
  - 승인 필요
  - pending 항목
  - 오류
  - wiki 개수
  - 시스템 상태
- Mapping Main
  - PC: 좌측 candidate queue + 우측 3-step workspace
  - Mobile: 단일 column stepper. 모바일에서도 `Reject + Retry`, `Confirm` 핵심 결정을 허용한다.
  - 기존 wiki match 목록과 `Use this wiki`/`Switch` 액션을 제공한다.
  - `Add to selected wiki`, `Merge into selected wiki`, `Create new`, `Confirm mapping` 버튼 액션을 명시적으로 제공한다.
  - 기존 wiki가 선택되지 않으면 Add/Merge는 disabled 상태로 안내한다.
  - steps: `Page 검증 → Page Mapping → Relationship 검증 → 오류/에러`
  - confirm은 Relationship 검증 이후 가능하다.
  - retry는 오류/에러 tab에서 instruction과 함께 실행한다.
  - Wiki compile preview는 필요 시 펼침
- Wiki graph
  - 선택 개념 중심 1-hop graph
  - `| graph | wiki 내용 |` 구조
- Settings
  - model 설정
  - prompt test version
  - test run
  - confirm version
  - change logging

## Excluded features

- 다중 사용자 권한
- 협업 승인 워크플로우
- 다중 사용자 메뉴/프로필 관리. 단, Logout 위치는 향후 사용자 메뉴 dropdown으로 예약한다.
- Web에서 Vault 무제한 직접 편집

## Tasks

1. Web stack 최종 선택
2. Auth 방식 선택
3. Dashboard API/데이터 계약 설계
4. Review candidate query/similarity sort 계약 설계
5. batch merge/new/retry action 계약 설계
6. Graph popup 1-hop query 계약 설계
7. Settings prompt versioning API 계약 설계
8. Mockup 기반 UI 구현 검증 항목 확정
9. PC/Mobile navigation, submenu, button token 검증 항목 확정

## Git checkpoint

- `phase-3-web-review-ui`

## Entry criteria

- Phase 1 CLI 상태/job/artifact 기반 존재
- Phase 2 review_route/human_decision/retry_instruction schema 존재
- HTML mockup 승인 완료

## Exit criteria

- Dashboard에서 pending/error/review/system status 확인 가능
- Review 화면에서 신규 개념 batch 처리 가능
- Graph popup에서 1-hop 관계와 wiki 내용 확인 가능
- Prompt 변경 이력과 test→confirm 흐름 작동
- PC와 Mobile 모두에서 top navigation, page submenu, 주요 CTA 위치/크기가 통합 UI 기준과 일치

## Phase 3 UI 일치성 보정 — 2026-07-19

- 사용자 결정: Phase 3 web UI는 통합 mockup 기준으로 통일한다.
- 사용자 결정: Mobile Mapping에서도 `Reject + Retry`, `Confirm`을 허용한다. Mobile은 단일 column stepper와 하단 sticky CTA를 사용한다.
- 사용자 결정: Logout은 top-level nav에 두지 않고 향후 사용자 메뉴 dropdown에 배치한다. 사용자 메뉴가 아직 없으므로 Build는 top nav에 Logout을 추가하지 않는다.
- PC 기본: 상단 global nav + 페이지별 좌측 또는 상단 submenu. Settings처럼 관리형 화면은 좌측 submenu 우선, 단 prompt task list 같은 2차 목록은 본문 안의 list/panel로 표현한다.
- Mobile 기본: compact header + 사이드 메뉴 버튼(☰), drawer 내부 nested submenu, 주요 CTA는 하단 sticky 영역.
- Mobile Mapping 주요 CTA에는 기존 wiki 매핑 액션(`Add/Merge/Create/Confirm`)이 반드시 포함된다.
- Mobile에서는 상단에 메뉴 항목을 여러 개 나열하지 않는다.
- Breakpoint 기준: desktop `>= 1024px`, tablet `768–1023px`, mobile `< 768px`.


## 확정 Web UI 기술스택

- Backend/API: FastAPI
- Server: uvicorn
- Template: Jinja2
- Forms: python-multipart
- Settings: PyYAML
- Env: python-dotenv
- Validation/schema: pydantic
- Frontend: server-rendered HTML + Vanilla JavaScript ES modules + plain CSS
- Graph popup: inline SVG + Vanilla JS
- Auth: `.env` 관리자 비밀번호 + stdlib hmac signed session cookie
- 제외: React/Vite/Next.js, Tailwind build pipeline, 외부 graph library 필수 의존, 다중 사용자 auth

Build agent는 위 dependency 추가를 승인된 것으로 본다. 이 목록 밖의 dependency가 필요하면 사용자 승인을 요청한다.
