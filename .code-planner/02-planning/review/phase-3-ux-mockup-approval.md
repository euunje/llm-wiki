# Phase 3 Revised UX Mockup Approval

## Approval status

- Status: `approved_for_build_fix`
- Approved by: user
- Approval note: “해당 목업으로 확정하고 구현시 방향이 바뀌지 않게하자”
- Date: 2026-07-19

## Approved mockup files

- Integrated mockup:
  - `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Onboarding mockup:
  - `.code-planner/02-planning/mockups/phase-3-page-onboarding-mockup.html`

## Approved UX spec files

- `.code-planner/02-planning/mockups/phase-3-page-onboarding-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-inbox-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-mapping-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-wiki-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-vault-browser-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-settings-llm-routes-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-settings-prompt-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-page-dashboard-ux-spec.md`
- `.code-planner/02-planning/mockups/phase-3-error-handling-navigation-ux-spec.md`

## Build implementation lock

Build must not change the approved UX direction without explicit user approval.

Locked decisions:

1. Top-level navigation:
   - `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings`
   - `Logout`은 top-level nav가 아니라 향후 사용자 메뉴 dropdown에 배치한다.
   - 사용자 메뉴가 아직 없으면 Build는 top nav에 Logout을 추가하지 않고, 필요 시 Settings > Auth 임시 액션으로만 제공한다.
2. PC-first design, tablet/mobile responsive.
   - Mobile은 상단 메뉴 나열이 아니라 좌측 사이드 메뉴 버튼(☰)으로 drawer를 열어 세부 메뉴에 진입한다.
3. Icon + short label + 1-line helper text design language.
4. Onboarding:
   - wizard step rail
   - provider → endpoint → API key → test → model select
   - fastembed embedding model selection
   - full-path file browser starting from home
5. Inbox:
   - upload/text/scan source input
   - internal pipeline hidden as automatic processing
   - processing log available
   - completed as result/audit record
6. Mapping:
   - 3-step wizard plus 오류/에러 tab
   - `Page 검증 → Page Mapping → Relationship 검증 → 오류/에러`
   - confirm only after Relationship 검증
   - retry with instruction in 오류/에러 tab
   - mobile에서도 `Reject + Retry`, `Confirm` 핵심 결정 액션 허용
   - mobile은 단일 column stepper + 하단 sticky CTA 사용
   - mobile step 전환은 사이드 drawer의 Mapping nested menu에서 접근 가능해야 함
7. Wiki:
   - TOC/list + Markdown viewer
   - mobile drawer TOC/search
   - graph at bottom
   - frontmatter hidden from main body
8. Vault Browser:
   - read-only folder/file/content viewer
   - Markdown viewer
   - no edit/new/delete/move
9. Settings LLM:
   - same basic setup as Onboarding
   - routes only as advanced options
   - default all chat tasks use same model
   - concurrent LLM tasks default 1, max 3
10. Settings Prompt:
    - active prompt status
    - Phase 2 default prompt visibility
    - version history at bottom
    - rollback creates new confirmed copy
    - no confirm-anyway for failed tests
11. Dashboard:
    - top cards: `Inbox / Mapping / Wiki / Vault / Issues`
    - no OS CPU/RAM in phase 1 dashboard scope
12. Errors:
    - no top-level Error menu
    - Dashboard issues summary + contextual page error handling

## Regression rule

If implementation cannot follow a locked UX decision, Build must stop and request user approval with:

- the affected decision
- reason it cannot be implemented as approved
- proposed alternative
- impact on existing mockup/spec

Build must not silently replace the approved layout with the older Phase 3 implementation.

## PRV review reference

- Tailnet PRV review URL opened for final review:
  - `http://100.66.135.34:46483/session/20260719T032700Z-82c3af`
- PRV package:
  - `.prv/opencode-review-package-1784431620078.json`
