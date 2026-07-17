# Phase 3 — Chunked extraction map-reduce

## 목적

큰 문서에서 context overflow 없이 후보 추출을 수행한다.

## 사용자에게 보이는 결과

- 큰 문서도 앞부분 truncate 없이 전체 범위에서 entity/concept 후보가 추출된다.

## 관련 목업/스펙

- Feature: `.code-planner/02-planning/features/feature-chunked-extraction.md`

## 포함 기능

- `ParsedDocument.chunks` 기반 chunk extraction.
- chunk-level JSON schema.
- chunk result aggregation/dedupe.
- chunk summary 기반 source page input.
- context overflow fallback.
- 기존 2-pass resolution/page generation 연결.

## 제외 기능

- Raw file physical chunk split.
- UI redesign.

## Build tasks

- prompt 추가/수정.
- extraction parser/aggregator helper.
- chunk failure/retry policy 구현.
- tests for long document.

## Git checkpoint

- `feat: add chunked extraction`

## Entry criteria

- Phase 1/2 source/inbox tracking available.

## Exit criteria

- context overflow 문서가 chunk mode로 처리됨.
- chunk 후반부 후보도 보존.
- aggregation 결과가 기존 resolution에 연결됨.
