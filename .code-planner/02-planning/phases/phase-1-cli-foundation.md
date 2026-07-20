# Phase 1 — CLI Foundation

## Purpose

LLM Wiki Local의 1차 목표인 CLI 기능 구현을 완성한다. 이 phase는 최종 wiki 품질보다 자료 처리, 설정, DB, artifact, LLM 연결, sync의 기반을 만드는 단계다.

## User-visible outcome

- 사용자가 로컬에서 `wiki init`으로 프로젝트 구조를 초기화한다.
- Markdown 자료를 CLI로 등록하고 chunk/embedding까지 처리한다.
- LLM endpoint 연결과 JSON/artifact 계약을 확인한다.
- SQLite에 Source/Chunk/Embedding/Job/Artifact 상태가 기록된다.
- `wiki sync`로 Vault와 DB 상태를 수동 확인한다.

## Related mockup

- not_applicable: Phase 1은 CLI 중심 phase이며 UI 목업 대상이 아니다.

## Included features

- Python CLI entrypoint
- `wiki init`
- `wiki settings get/set`
- `wiki doctor`
- `wiki inbox scan`
- `wiki ingest`, `wiki ingest-text`
- `wiki normalize`
- `wiki chunk`
- `wiki embed`
- `wiki models list/test`
- `wiki route get/set`
- `wiki extract-claims` 최소 JSON/artifact 계약
- `wiki validate`, `wiki lint`, `wiki status`, `wiki search` 기본
- `wiki fix`, `wiki retry`, `wiki sync`
- `wiki ask`, `wiki map`, `wiki summarize`, `wiki compile`은 최소 계약/placeholder 수준

## Excluded features

- 실제 LLM wiki 프롬프트 품질 완성
- 실사용 WikiPage 품질
- PDF/Office/HTML/URL 완성 지원
- Web UI
- 자동 file watcher sync

## Tasks

1. Python package와 CLI command router 설계
2. Settings/sample env 구조 설계
3. SQLite schema와 migration 초기 구조 설계
4. Vault/data 폴더 구조 생성 로직 설계
5. Job/AgentRun/Artifact 기록 계약 설계
6. Markdown ingest/normalize/chunk 구현 범위 확정
7. fastembed embedding 저장 계약 확정
8. LLM endpoint 연결 테스트와 JSON schema validation 계약 확정
9. sync 기본 dry-run, 실제 반영은 --apply 정책 적용

## Git checkpoint

- `phase-1-cli-foundation`

## Entry criteria

- `.code-planner/01-ideation-approved.json` 존재
- ADRs/dependencies/git-plan 작성 완료
- Phase 1 feature contract 작성 완료

## Exit criteria

- 샘플 Markdown 1건이 `ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync` 흐름을 통과할 수 있도록 설계/구현됨
- 모든 CLI 명령의 최소 입출력/실패/재실행 계약이 문서화됨
- Web UI 없이도 CLI만으로 상태 확인 가능


## 확정 보정

- Settings 파일 형식: YAML
- `wiki sync`: 기본 dry-run/report, 실제 반영은 `--apply`
- Web Auth secret은 `.env`에 둔 사용자 비밀번호 기반
