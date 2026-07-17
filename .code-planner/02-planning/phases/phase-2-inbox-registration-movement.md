# Phase 2 — Inbox registration and file movement

## 목적

사용자 입력을 Inbox item으로 등록하고, 성공/실패/리뷰/Archive 이동의 파일 흐름을 구현한다.

## 사용자에게 보이는 결과

- 파일/Markdown/붙여넣기 텍스트가 Raw Sources가 아니라 Inbox에 등록된다.
- 실패 원본은 `_Failed`, 리뷰 대상은 `_Review`, 성공 원본은 Raw archive로 이동한다.

## 관련 목업/스펙

- Feature: `.code-planner/02-planning/features/feature-inbox-registration.md`
- Mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.md`

## 포함 기능

- 세 입력 유형 등록.
- Inbox → `processing` DB state/lock.
- success → Raw archive move.
- failure → Inbox/_Failed move + diagnostic report.
- review → Inbox/_Review move.
- 파일명 충돌/중복 hash 처리.
- 권장 입력 하위 폴더: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.

## 제외 기능

- Review workbench action 상세.
- chunked extraction map-reduce.

## Build tasks

- `ingest_raw.py` 역할 조정 또는 inbox registration helper 추가.
- Web upload/paste API를 Inbox 등록으로 전환.
- CLI add semantics 조정.
- move failure handling.
- Failed report format 구현.

## Git checkpoint

- `feat: route inputs through inbox`

## Entry criteria

- Phase 1 상태 모델 존재.

## Exit criteria

- 입력 3유형이 Inbox item으로 등록됨.
- 성공/실패/review 이동이 테스트됨.
- 실패 로그가 생성되고 삭제 가능.

## Known limitation carried to Phase 5A

- Phase 2 registration may create `inbox_items` before processing, but existing job/LLM pipeline still expects `sources.id`.
- Therefore `inbox_items.source_id` can be `NULL` until processing starts.
- This is acceptable only if Phase 5A implements `inbox_item_id -> source_id -> ingest_job` mapping before UX/E2E testing.
