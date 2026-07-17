# Stage 1 — 기술 논의

## Gate input

- Ideation artifact: `.code-planner/01-ideation-approved.json`
- Gate status: passed
- User decisions:
  - 실행 환경: local Linux + Obsidian vault + FastAPI Web UI + CLI
  - 기술 방향: **Inbox item DB + 파일 이동 하이브리드**
  - Git 운영: 이미 분리된 현재 브랜치에서 phase별 작업

## 문제 정의

현재 구조는 `Raw Sources -> ingest -> Wiki` 중심이다. 사용자는 새 입력을 Raw Sources에 직접 넣거나 Web ingest가 raw로 업로드한 뒤 처리한다. 이 구조에서는 다음 문제가 있다.

- Inbox가 입력/검토 중심으로 작동하지 않는다.
- Raw Sources가 사용자 입력점과 archive 역할을 동시에 한다.
- 실패/리뷰/처리중 상태가 파일 위치와 DB 상태에서 명확히 분리되지 않는다.
- parser는 chunks를 만들지만 LLM extraction은 `parsed.chunks`가 아니라 긴 `parsed.text`를 잘라 사용한다.
- 큰 문서에서 LM Studio/OpenAI-compatible context overflow가 발생한다.

## 기술 선택지

### A. 기존 `non_categories` 확장 중심

- 설명: 기존 `non_categories`/Inbox UI와 frontmatter 중심으로 상태를 관리한다.
- 장점: 구현량이 적고 기존 promote/relinker를 재사용하기 쉽다.
- 단점: source-level 상태, candidate-level 상태, failure log가 파일 frontmatter에 흩어진다. 동시성/재시도/이동 실패 처리에 약하다.

### B. Inbox item DB + 파일 이동 하이브리드 — 선택

- 설명: 원본 파일은 Inbox/Raw archive 사이에서 이동하고, 상태 전이는 DB로 관리한다. Review/Failed 작업물은 폴더와 DB 양쪽에서 추적한다.
- 장점:
  - `pending/processing/failed/review/archived/ingested` 흐름이 명확하다.
  - Web UI와 CLI가 같은 상태 모델을 공유한다.
  - 실패 로그, retry, 중간 장애 복구, 파일명 충돌을 추적하기 쉽다.
  - chunked extraction 결과와 candidate review 상태를 구조화하기 쉽다.
- 단점: DB schema migration과 기존 `sources`/`ingest_jobs` 연동 설계가 필요하다.

### C. 모든 후보 Markdown review-first

- 설명: 모든 LLM 후보를 Wiki 반영 전 `_Review`에 저장하고 사람이 승인해야 한다.
- 장점: 매우 안전하다.
- 단점: 자동화 가치가 크게 줄고, 사용자가 모든 후보를 검토해야 한다.

## 선택

**B. Inbox item DB + 파일 이동 하이브리드**를 채택한다.

## 설계 원칙

- Inbox는 사용자 입력 지점이다.
- Raw Sources는 처리 완료 원본 archive다.
- 실패 원본은 `Inbox/_Failed`로 이동한다.
- Review 원본/후보는 `Inbox/_Review`로 이동한다.
- 성공 기준은 Planning에서 더 구체화하되 기본 방향은 “Wiki 반영 성공 + Raw archive 이동 성공”이다.
- 원본 raw는 chunk별로 물리 분할하지 않는다.
- chunk는 processing 내부 단위이며 DB/runtime metadata로 관리한다.
- Review UI는 유사 Wiki 편입 선택지와 별도 태깅/분류 입력 폼을 제공한다.
- reset은 제품 기능이 아니라 이번 테스트 전 qmd/Obsidian 값 일회성 초기화로만 취급한다.

## 주요 기술 논점

1. DB schema
   - `sources`는 archive된 원본 중심으로 유지할지, Inbox item과 통합할지 결정 필요.
   - 추천: `inbox_items`를 추가하고, 성공 archive 후 `sources`와 연결한다.

2. 파일 위치 상태
   - Inbox incoming → processing lock → success archive / failed / review.
   - move 실패, 파일명 충돌, 중복 처리, 동시 처리 lock 필요.

3. chunked extraction
   - `ParsedDocument.chunks`를 chunk별 extraction에 사용한다.
   - chunk summaries/candidates를 aggregate한 뒤 기존 2-pass resolution/page generation에 연결한다.

4. UI/UX
   - Web UI는 Files/Markdown/Text 입력, 상태 목록, Failed 로그, Review 편입 작업대를 제공해야 한다.
   - Planning Stage 4에서 HTML mockup과 Lavish review 필요.

5. CLI
   - CLI도 Inbox 추가/처리/상태/재시도 흐름을 제공해야 한다.
