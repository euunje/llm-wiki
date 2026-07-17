# Phase 1 — Inbox domain model and path/state foundation

## 목적

Inbox-first ingest의 공통 상태 모델과 path 의미를 확정한다.

## 사용자에게 보이는 결과

- 시스템이 Raw Sources를 입력점이 아닌 archive로 취급할 준비가 된다.
- Inbox item의 상태가 DB에서 추적된다.

## 관련 목업/스펙

- Feature: `.code-planner/02-planning/features/feature-inbox-domain.md`
- UI mockup: not applicable in this phase

## 포함 기능

- Inbox item 상태 모델.
- DB schema/migration 설계.
- Path mapping 확정.
- `processing`은 실제 폴더가 아니라 DB 상태/lock으로 정의한다.
- `sources`와 Inbox item의 관계 정의.
- 상태 이벤트 모델.

## 제외 기능

- 실제 Web UI 화면 변경.
- chunked extraction 구현.
- Review/Failed action 구현.

## Build tasks

- `db.py` schema migration 설계/구현.
- `config.py` path semantics 정리.
- domain helper 추가.
- 기존 tests와 Ja layout 호환 확인.

## Git checkpoint

- `feat: add inbox domain model`

## Entry criteria

- Stage 1~3 기술/phase 결정 승인.

## Exit criteria

- DB migration idempotent.
- Inbox state enum과 event 모델이 문서/코드에 일치.
- 기존 raw/source 흐름 회귀 없음.
- 실제 `_Processing` 폴더 없이 동시 처리 lock 의미가 명확함.
