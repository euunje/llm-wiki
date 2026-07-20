# Handoff Change Requests Response

## Source

- PRV session: `20260718T020131Z-51d6e9`
- Decision: changes_requested
- Request count: 3

## 요청 1. init 폴더 구조 정의 필요

반영 완료.

- 새 문서: `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
- 핵심 구조:
  - `vault/00_Inbox/`
  - `vault/10_Wiki/`
  - `vault/20_Review/`
  - `vault/80_Raws/`
  - `vault/90_Settings/`
  - `data/raw/`, `data/normalized/`, `data/artifacts/`, `data/exports/`, `data/cache/`

## 요청 2. LLM 연결 테스트 커맨드 위치 불명확

반영 완료.

- `wiki doctor`: 환경 점검
- `wiki models test <model_id>`: LLM/chat/embedding endpoint 실제 연결 테스트
- CLI 명세와 E2E 테스트 플랜에 명시

## 요청 3. Build 목표와 기능별 E2E 테스트 플랜 미흡

반영 완료.

- 새 문서: `.code-planner/02-planning/validation/cli-e2e-test-plan.md`
- 포함된 E2E:
  - Init
  - Markdown ingest pipeline
  - Unsupported input guard
  - Embedding
  - LLM 연결 테스트
  - LLM candidate contract
  - Sync dry-run/apply
  - Retry with instruction
  - Compile placeholder
  - Healthcheck

## Handoff 반영

- `.code-planner/02-planning/handoff/build-handoff.md`에 PRV 수정 요청 반영 섹션 추가
