# 01 Phase Plan — Inbox-first ingest flow

## Phase order

| Phase | Name | Goal | Main validation |
|---|---|---|---|
| 1 | Inbox domain model and path/state foundation | DB 상태 모델과 path 의미 확정 | migration/idempotency/path compatibility |
| 2 | Inbox registration and file movement | Files/Markdown/Text 등록 및 성공/실패/review 이동 | move semantics, failed report, no data loss |
| 3 | Chunked extraction map-reduce | 큰 문서 context overflow 해결 | 100k+ chars, chunk aggregation, progress |
| 4 | Review/Failed workbench behavior | `_Review`/`_Failed` 작업대 구현 | routing conditions, actions, diagnostics |
| 5A | Inbox-to-Job dispatch mapping | Inbox item을 기존 source/job/LLM pipeline에 연결 | `inbox_item_id -> source_id -> ingest_job`, Raw Sources import-to-Inbox |
| 5B | CLI/Web UI integration | `/ingest`, `/inbox`, `/jobs`, CLI 일관화 | Web/CLI parity, PRV mockup match |
| 6 | Test reset guide and E2E validation | 일회성 테스트 준비와 E2E 증적 | E2E matrix, reset non-product guarantee |

## Key dependencies

- Phase 2 depends on Phase 1 state/path model.
- Phase 3 depends on Phase 1/2 source tracking and failure routing.
- Phase 4 depends on Phase 1/2 and consumes Phase 3 review/failure outcomes.
- Phase 5A depends on Phase 1~4 backend behavior and closes the current Inbox pending -> job dispatch gap.
- Phase 5B depends on Phase 5A because UX testing is invalid until pending Inbox items can actually process.
- Phase 6 validates all previous phases.

## Important fixed decisions

- `processing` is DB state/lock, not an `Inbox/_Processing` folder.
- Input folder conventions: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- Review detailed actions are Web UI first.
- CLI required scope: `wiki add`, `wiki ingest`, `wiki status`, `wiki retry <inbox_item_id>`.
- Raw Sources is archive, not the normal queue. Existing Raw Sources files are imported into Inbox for processing.
- Internal dispatch may materialize/reuse `sources` rows, but user-visible queue is Inbox.
- Jobs must show chunk extraction phase/progress.

## Source phase docs

- `.code-planner/02-planning/phases/phase-1-inbox-domain.md`
- `.code-planner/02-planning/phases/phase-2-inbox-registration-movement.md`
- `.code-planner/02-planning/phases/phase-3-chunked-extraction.md`
- `.code-planner/02-planning/phases/phase-4-review-failed-workbench.md`
- `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
