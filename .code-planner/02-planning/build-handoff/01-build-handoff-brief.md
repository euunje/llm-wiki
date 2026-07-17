# 01 Build Handoff Brief — Inbox-first ingest flow

## Status

- Source handoff: `.code-planner/02-planning/handoff/build-handoff.md`
- Approval: PRV confirmed, session `20260715T121805Z-371ffe`
- Purpose: Build 도구가 요구하는 표준 경로용 handoff brief.

## Build objective

`llm-wiki` ingest 흐름을 다음 구조로 바꾼다.

```text
Inbox -> ingest/process -> Wiki + Raw Sources archive
```

## Non-negotiable requirements

- Inbox가 사용자 입력 지점이다.
- Raw Sources는 성공 처리된 원본 archive다.
- 기존 Raw Sources 문서는 정상 처리 queue가 아니라 Inbox로 가져오는 import/migration 대상이다.
- UX 테스트는 `Inbox pending -> source/job materialization -> LLM 처리`가 통과된 뒤에만 진행한다.
- 실패 원본은 `Inbox/_Failed`로 이동하고 diagnostic report를 남긴다.
- Review 대상은 `Inbox/_Review`로 이동한다.
- 큰 문서는 `ParsedDocument.chunks` 기반 chunked extraction map-reduce로 처리한다.
- 원본 raw 파일은 chunk별로 물리 분할하지 않는다.
- qmd/Obsidian reset은 제품 기능으로 구현하지 않는다.
- 기존 `/ingest`, `/inbox`, `/jobs` UX 패턴을 유지한다.

## Build phases

1. Inbox domain model and path/state foundation
2. Inbox registration and file movement
3. Chunked extraction map-reduce
4. Review/Failed workbench behavior
5A. Inbox-to-Job dispatch mapping
    - `inbox_item_id -> source_id -> ingest_job` 연결.
    - Raw Sources action은 직접 queue scan이 아니라 Inbox로 가져오기.
    - 이 단계가 pass되기 전 UX 테스트 금지.
5B. CLI/Web UI integration
    - `/ingest`, `/inbox`, `/jobs`, CLI가 같은 Inbox 상태 모델을 표시.
    - PRV-confirmed mockup과 구현 UX 일치.
6. Test reset guide and end-to-end validation

## Canonical planning references

- Phase overview: `.code-planner/02-planning/phases/01-phase-plan.md`
- Detailed phase tasks: `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- Phase 1 doc: `.code-planner/02-planning/phases/phase-1-inbox-domain.md`
- Phase 2 doc: `.code-planner/02-planning/phases/phase-2-inbox-registration-movement.md`
- Phase 3 doc: `.code-planner/02-planning/phases/phase-3-chunked-extraction.md`
- Phase 4 doc: `.code-planner/02-planning/phases/phase-4-review-failed-workbench.md`
- Validation: `.code-planner/02-planning/validation/01-validation-plan.md`
- ADRs: `.code-planner/02-planning/decisions/ADRs.md`
- Dependencies: `.code-planner/02-planning/decisions/dependencies.md`
- Git plan: `.code-planner/02-planning/git/git-plan.md`
- Phase 5 doc: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- Phase 5 mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.md`
- Phase 5 HTML: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html`
