# Phase 4 — Review/Failed workbench behavior

## 목적

`Inbox/_Review`와 `Inbox/_Failed`를 사용자가 처리 가능한 작업대로 만든다.

## 사용자에게 보이는 결과

- Review item에서 유사 Wiki 편입 후보를 보고 선택할 수 있다.
- 편입 대상이 없으면 별도 태깅/분류 입력 폼을 사용한다.
- Failed item에서 원인 로그를 보고 재시도/삭제/보류를 선택할 수 있다.

## 관련 목업/스펙

- Feature: `.code-planner/02-planning/features/feature-review-failed-workbench.md`
- Markdown mockup: `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.md`
- HTML mockup: `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.html` (created and PRV-confirmed)

## 포함 기능

- Review routing conditions. Source of truth:
  - fuzzy duplicate/merge ambiguity
  - multiple exact/near matches
  - low/ambiguous/pending confidence
  - entity/concept classification ambiguity
  - guide/runbook/map/MOC 등 canonical Wiki page로 바로 넣기 어려운 내용
  - JSON validation failed after retry
  - allowed_links violation or links_used/body wikilink mismatch
  - source reference missing/unclear
  - source/canonical slug conflict
  - chunk extraction conflict
  - human-approved merge/update required
- Similarity candidates display data.
- Edit/tag/classify form data contract.
- Review approve/reprocess/hold/delete actions.
- Failed diagnostics and retry/delete/log delete actions.

## 제외 기능

- New design system.
- Raw physical chunk split.

## Build tasks

- `webapp/routes/inbox.py` expansion.
- `templates/inbox.html` extension using existing layout.
- API endpoints for review/failed actions.
- DB state/event updates.
- relinker/promote integration.

## Git checkpoint

- `feat: add inbox review workbench`

## Entry criteria

- Phase 1/2 state and movement available.

## Exit criteria

- Review and Failed flows usable in Web UI.
- Similarity candidate and tag form contract tested.
- Failed logs can be inspected and removed after handling.
