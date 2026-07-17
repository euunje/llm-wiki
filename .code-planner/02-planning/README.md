# 02 Planning — Inbox-first ingest flow

## 입력 Ideation

- Source: `.code-planner/01-ideation-approved.json`
- Project: `llm-wiki inbox-first ingest flow`
- Planning readiness: `ready`
- User approval: `approved`

## 목표

`llm-wiki`의 ingest 구조를 현재 `Raw Sources -> ingest -> Wiki` 중심에서 `Inbox -> ingest/process -> Wiki + Raw Sources archive` 중심으로 재정비한다.

## 확정된 방향

- Inbox가 사용자 입력 지점이다.
- Raw Sources는 처리 대기열이 아니라 **성공 처리된 원본 archive**다.
- 기존 vault의 `10. Raw Sources`/Raw Sources 문서는 정상 queue가 아니라 **Inbox로 가져오기(import/migration)** 대상이다.
- 입력 유형은 3가지다.
  1. 문서파일: PDF/DOCX/PPTX 등
  2. Markdown/Obsidian 스크랩
  3. 사용자 붙여넣기 텍스트
- 성공한 원본은 `Raw Sources` archive로 이동한다.
- 실패한 원본은 `Inbox/_Failed`로 이동하고 원인 파악 로그/리포트를 남긴다.
- 오류 확인/처리 후 Failed 로그는 삭제 가능해야 한다.
- Review 대상은 `Inbox/_Review`로 이동한다.
- Review UI는 기존 Wiki 유사 항목 편입 선택지와 별도 태깅/분류 입력 폼을 제공한다.
- 원본 raw는 chunk별 물리 분할 저장하지 않는다.
- 큰 문서는 `ParsedDocument.chunks` 기반 chunked extraction map-reduce로 처리한다.
- CLI/Web UI 전체 흐름 재정비가 범위다.
- qmd/Obsidian 값 reset은 반복 기능이 아닌 이번 테스트 전 일회성 초기화로 본다.
- 처리 실행은 사용자 관점에서 `Inbox -> LLM 확인/처리 -> Wiki 문서화 -> Raw Sources archive`로 보인다.
- 내부 구현은 기존 `sources`/`jobs`/`ingest_llm.ingest_source(source_id)`를 재사용하되, 처리 시작 시 `inbox_item_id -> source_id` 연결을 생성/저장한다.

## 현재 코드 탐색 요약

- `src/llm_wiki/config.py`: `WikiPaths`, `raw`, `non_categories` 등 path config 중심.
- `src/llm_wiki/ingest_raw.py`: 현재 파일을 raw로 복사/등록하는 plumbing.
- `src/llm_wiki/ingest_llm.py`: extraction -> draft -> source page ingest pipeline.
- `src/llm_wiki/parsers/base.py`: `ParsedDocument.chunks`는 이미 존재.
- `src/llm_wiki/webapp/routes/inbox.py`: 현재는 `non_categories/*.md` promote/delete 중심의 최소 Inbox UI.
- `src/llm_wiki/webapp/routes/ingest.py`: 현재 web upload/scan/start는 raw 중심.
- `src/llm_wiki/jobs.py`: persistent ingest job/SSE 진행 상태.
- `src/llm_wiki/db.py`: 현재 sources/jobs/runs/pages/logs 테이블 중심, candidate-level review 상태는 없음.

## Planning 상태

- Stage 1 기술 논의: 완료
- Stage 2 기술 확정: 완료
- Stage 3 Phase 설계: 승인됨
- Stage 4 UI/UX 목업: PRV confirmed
- Stage 5 Phase fix: 완료
- Stage 6 Validation plan: 완료
- Stage 7 Crosscheck: passed with documented defaults
- Stage 8 Build handoff: approved
- Stage 8 보정: Raw Sources archive 의미와 Phase 5A Inbox-to-Job 연결 gap 반영 완료(2026-07-16 사용자 확인).
- PRV feedback: `.code-planner/02-planning/review/phase-map-prv-feedback.md`
- Phase 4/5 PRV feedback: `.code-planner/02-planning/review/phase-4-5-prv-feedback.md`
- Final Build handoff PRV feedback: `.code-planner/02-planning/review/final-build-handoff-prv-feedback.md`
- Build-gate compatibility PRV feedback: `.code-planner/02-planning/review/build-gate-compatibility-prv-feedback.md`
- Raw Sources → Inbox realignment PRV feedback: `.code-planner/02-planning/review/raw-sources-inbox-realignment-prv-feedback.md`

## Stage 1 기술 옵션 초안

아래 옵션 중 하나를 기준으로 Stage 2 ADR/dependencies/git-plan을 작성한다.

| 선택지 | 적합한 경우 | 장점 | 단점 | 예시 | 추천도 |
|---|---|---|---|---|---|
| A. 기존 `non_categories` 확장 중심 | 빠른 전환, 기존 구조 최대 재사용 | 구현량 적음, 기존 promote/relinker 활용 | candidate/review 상태가 파일 frontmatter에 흩어질 수 있음 | `Inbox/_Review/*.md`, `Inbox/_Failed/*.md` 파일 기반 | 중간 |
| B. Inbox item DB + 파일 이동 하이브리드 | 상태 전이/재시도/동시성/로그가 중요 | Processing/Failed/Review/Wiki 상태 관리 명확, Web/CLI 일관성 좋음 | DB schema/마이그레이션 필요 | `inbox_items`, `candidate_reviews`, 원본 파일 path tracking | 높음(추천) |
| C. 모든 후보를 Markdown review-first로 저장 | 사람이 모든 편입을 검토해야 함 | 안전하고 Obsidian 친화적 | 자동 ingest 가치 감소, UI 복잡도 증가 | 모든 entity/concept 후보를 `_Review`에서 승인 후 promote | 낮음~중간 |

## 현재 추천

**B. Inbox item DB + 파일 이동 하이브리드**를 추천한다.

이유:
- 실패/리뷰/처리중/성공 상태 전이가 핵심 요구사항이다.
- move 기반 파일 흐름은 중간 장애와 재시도 상태를 DB로 추적해야 안전하다.
- Web UI와 CLI 모두 같은 상태 모델을 공유해야 한다.
- chunked extraction map-reduce 결과와 후보별 review 상태는 파일 frontmatter만으로 관리하기 어렵다.

## 확정된 기술 결정

1. 실행 환경: local Linux + Obsidian vault + FastAPI Web UI + CLI.
2. 기술 방향: B. Inbox item DB + 파일 이동 하이브리드.
3. Git 운영: 이미 분리된 현재 브랜치에서 phase별 commit.
4. Raw Sources 의미: 입력 queue가 아니라 처리 완료 원본 archive. 기존 자료는 `/ingest`에서 “Raw Sources에서 Inbox로 가져오기”로 등록한다.
5. Inbox-to-Job 연결: `inbox_item_id`를 처리 시작 시 내부 `sources.id`로 materialize/link하고 기존 job/LLM pipeline을 재사용한다.
6. Raw Sources → Inbox realignment approval: PRV session `20260716T072651Z-01bdca`.

## 다음 단계

- Build 단계로 전환 가능.
