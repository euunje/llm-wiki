# Phase 6 — Test reset guide and end-to-end validation

## 목적

일회성 테스트 초기화와 전체 end-to-end 검증 절차를 안전하게 문서화하고 수행한다.

## 사용자에게 보이는 결과

- qmd/Obsidian 값 초기화 후 Inbox 기반 재처리 테스트를 안전하게 할 수 있다.
- reset은 제품 명령으로 구현되지 않는다.

## 관련 목업/스펙

- N/A

## 포함 기능

- 테스트 초기화 절차 문서.
- 기존 Wiki 자료 삭제/초기화 주의사항.
- 기존 Raw 자료를 Inbox로 실제 move해 테스트하는 절차.
- E2E test matrix.

## 제외 기능

- 반복 가능한 reset command.
- 운영 자동 reset.

## Build tasks

- docs/test guide 작성.
- E2E validation checklist 작성.
- manual test evidence paths 정의.

## Git checkpoint

- `test: document inbox flow validation`

## Entry criteria

- Phase 1~5 complete.

## Exit criteria

- 사용자가 실제 vault에서 end-to-end 테스트 가능.
- 데이터 삭제/초기화 위험이 명시됨.
- 테스트 evidence가 남음.
