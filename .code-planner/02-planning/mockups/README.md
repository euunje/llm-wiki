# Mockups — LLM Wiki Local

## 공식 UI/UX artifact 안내

Build agent 호환성을 위해 현재 승인된 Web Review 목업을 두 경로에 둔다.

## Canonical current mockup

- `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`
- `.code-planner/02-planning/mockups/phase-3-web-review-mockup.md`
- 승인 기록: `.code-planner/02-planning/review/phase-3-prv-feedback.md`

## Build gate compatibility mockup

일부 Build gate가 legacy phase-2/Lavish 이름을 요구하므로, 아래 파일을 compatibility artifact로 제공한다.

- `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`

주의:

- `phase-2-review-workspace.html`은 새 목업이 아니라, 승인된 `phase-3-web-review-mockup.html`과 동일한 Review Workspace 목업이다.
- 실제 리뷰는 PRV로 수행되었다.
- legacy 파일명에 `lavish`가 들어가지만, 현재 Planning workflow에서는 PRV review가 공식 리뷰 수단이다.

## 승인된 Review UX 요약

- 로그인 → Dashboard
- Dashboard: 자료 처리 현황, 승인 필요, pending, 오류, wiki 개수, 시스템 상태
- Review Main:
  - 왼쪽: 기존 wiki 유사도 목록
  - 가운데: 선택한 기존 개념 내용
  - 오른쪽: 신규 개념 batch 카드
- Graph popup: 선택 개념 중심 1-hop graph + wiki 내용
- Settings: prompt test version → test run → confirmed version
