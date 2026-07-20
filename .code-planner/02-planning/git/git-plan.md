# Git Plan — LLM Wiki Local

## Git remote

- 후보 remote: `git@github.com:euunje/llm-wiki-local.git`

## 운영 방식

- 기본 전략: 단일 브랜치 + phase별 commit
- 이유:
  - 단일 사용자 로컬 프로젝트에 적합하다.
  - phase별 검증/회귀 지점을 만들기 쉽다.

## commit checkpoint 후보

1. Planning docs 확정
2. Phase 1 CLI foundation
3. Phase 1 CLI E2E validation
4. Phase 2 LLM prompt/schema/page quality
5. Phase 3 Web UI dashboard/review
6. Validation fixes

## 주의

- Planning 단계에서는 git commit/push를 수행하지 않는다.
- Build 단계에서 사용자가 요청할 때만 commit/push를 수행한다.
- secrets 또는 실제 `.env`는 commit하지 않는다.
- sample env만 문서화/추가한다.
