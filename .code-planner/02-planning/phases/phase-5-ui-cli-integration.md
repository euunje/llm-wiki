# Phase 5 — Inbox-to-Job dispatch and CLI/Web UI integration

## 목적

Inbox-first 흐름을 실제 처리 pipeline까지 연결하고, Web UI와 CLI에서 일관되게 사용할 수 있게 한다.

## 사용자에게 보이는 결과

- `/ingest`에서 Files/Markdown/Text를 Inbox로 등록한다.
- 기존 `vault/10.Raw Sources`/Raw Sources 문서는 “Inbox로 가져오기”로 등록한다.
- Inbox pending item을 처리 시작하면 내부적으로 source/job이 생성/연결되고 LLM 처리가 시작된다.
- `/inbox`에서 Review/Failed를 처리한다.
- `/jobs`에서 Inbox item processing 상태를 확인한다.
- CLI에서도 add/ingest/status/retry 흐름을 사용할 수 있다.

## 관련 목업/스펙

- Feature: `.code-planner/02-planning/features/feature-ui-cli-integration.md`
- Markdown mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.md`
- HTML mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html` (created and PRV-confirmed)

## 포함 기능 — Phase 5A: Inbox-to-Job dispatch mapping

- `inbox_item_id -> source_id -> ingest_job` mapping.
- 처리 시작 시 `sources` row 생성/재사용 및 `inbox_items.source_id` 저장.
- `/ingest/start` 또는 equivalent API가 `inbox_item_id`를 primary key로 받음.
- 기존 `jobs.enqueue(source_id)`와 `ingest_llm.ingest_source(source_id)`를 재사용하는 adapter.
- Raw Sources scan은 `sources` 직접 등록이 아니라 Inbox pending import로 동작.
- 기존 Raw Sources 문서 기반 테스트는 “Raw Sources -> Inbox import -> process” 순서로 수행.

## 포함 기능 — Phase 5B: UI/CLI integration

- `/ingest` screen existing UX extension.
- `/inbox` filters/tabs and actions.
- `/jobs` inbox item display.
- Chunk extraction progress display in `/jobs` and live job stream.
- CLI command semantics update.
- CLI retry 최소 지원: `wiki retry <inbox_item_id>`.
- Review 상세 처리는 Web UI 중심. CLI는 status/count/link hint 수준.
- Web/CLI parity tests.

## 제외 기능

- Completely new UX layout.
- Reset command.

## Build tasks

- Core route adapter: Inbox item 처리 시작 -> sources row/link -> job enqueue.
- Raw Sources import route: Raw Sources 파일 -> Inbox item 등록, no direct queue.
- Templates/routes update.
- CLI help and command behavior update.
- Job events include inbox item metadata.
- Job events include chunk extraction phase/progress metadata.
- User-facing copy update.

## Git checkpoints

- Phase 5A: `feat: connect inbox items to ingest jobs`
- Phase 5B: `feat: integrate inbox flow in ui and cli`

## Entry criteria

- Phase 1~4 backend and workbench behavior available.

## Exit criteria

- Inbox pending item can start an ingest job without requiring user-visible `source_id`.
- Raw Sources import creates Inbox pending items and does not bypass Inbox.
- Web and CLI expose the same core flow.
- Existing UX style preserved.
- PRV/Lavish-reviewed HTML mockup reflected.
- Chunk progress display matches job event data.
