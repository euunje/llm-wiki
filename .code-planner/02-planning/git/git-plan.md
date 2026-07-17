# Git Plan

## Strategy

- 현재 분리된 브랜치에서 phase별 commit.
- 각 commit은 독립 검증 가능해야 한다.
- 이전 2-pass generation source 변경과 이번 Inbox-first planning scope가 같은 워크트리에 공존하므로 Build 시작 전 변경 범위를 확인한다.

## Recommended commits

1. `feat: add inbox domain model`
   - DB/path/state/event model.
2. `feat: route inputs through inbox`
   - file/markdown/text registration and movement.
3. `feat: add chunked extraction pipeline`
   - parser chunks, map-reduce extraction, progress events.
4. `feat: add inbox review workbench`
   - Review/Failed API and UI behavior.
5. `feat: connect inbox items to ingest jobs`
   - `inbox_item_id -> source_id -> ingest_job` mapping and Raw Sources import-to-Inbox.
6. `feat: integrate inbox flow in ui and cli`
   - `/ingest`, `/inbox`, `/jobs`, CLI add/ingest/status/retry UX and copy.
7. `test: document reset and e2e validation`
   - one-time reset guide and evidence matrix.

## Pre-commit checks per phase

- Inspect `git status` and diff.
- Stage only intended files.
- Run required validation checks from `validation/validation-plan.md`.
- Save evidence under `.code-planner/03-build/evidence/phase-*` during Build.
