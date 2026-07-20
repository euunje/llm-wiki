# ADRs — LLM Wiki Local

## ADR-001: Python 기반 CLI 우선 구조

- 상태: Accepted
- 결정: 1차 구현은 Python 기반 CLI 기능 구현을 중심으로 한다.
- 이유:
  - 로컬 LLM/embedding 생태계와 호환성이 좋다.
  - SQLite, FTS5, sqlite-vec 연동이 용이하다.
  - CLI → API/Web UI로 확장하기 쉽다.
- 결과:
  - 모든 1차 기능은 CLI 명령과 내부 service/job 계약을 기준으로 설계한다.
  - Web UI는 3차지만, CLI 결과와 job/artifact 구조를 재사용할 수 있게 한다.

## ADR-002: Obsidian Vault + SQLite 분리 저장

- 상태: Accepted
- 결정: 사람이 읽고 수정하는 지식 문서는 Obsidian Vault에 두고, 시스템 상태/검색/작업 기록은 SQLite에 둔다.
- 이유:
  - Vault는 사람이 직접 검토·수정하기 좋다.
  - SQLite는 job, artifact, embedding, FTS, relation, review 상태 관리에 적합하다.
- 결과:
  - 1차 동기화는 수동 `wiki sync`로 시작한다.
  - 자동 file watcher는 1차 범위에서 제외한다.

## ADR-003: 1차 입력은 Markdown only

- 상태: Accepted
- 결정: 1차 ingest/normalize는 Markdown만 완성 지원한다.
- 이유:
  - CLI 기반과 schema 안정화가 우선이다.
  - PDF/Office/HTML/URL 변환은 변환 품질과 예외 처리가 크다.
- 결과:
  - PDF/Office/HTML/URL 변환은 2차에서 `markitdown` adapter 후보로 설계한다.

## ADR-004: Embedding 기본값

- 상태: Accepted
- 결정: 1차 embedding 기본값은 `fastembed`와 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`로 둔다.
- 이유:
  - 한국어/영어 혼합 지식에 대응할 수 있다.
  - 로컬 실행에 적합하다.
- 결과:
  - dimension, model version, generated_at, target ref를 저장해야 한다.
  - 모델 교체 시 재임베딩/재인덱싱 정책은 planning validation에서 다룬다.

## ADR-005: LLM 런타임은 열린 설정

- 상태: Accepted
- 결정: claim 추출/매핑용 LLM 런타임은 특정 provider에 고정하지 않고 열린 설정으로 둔다.
- 이유:
  - 로컬 LLM, OpenAI-compatible endpoint, 기타 adapter 교체 가능성을 유지한다.
- 결과:
  - sample env를 제공한다.
  - Web Settings에서 model/prompt 설정과 prompt 버전관리, 변경점 logging을 고려한다.

## ADR-006: Web Review UX는 Planning에서 목업 필수

- 상태: Accepted
- 결정: Web Review UX는 Planning 단계에서 HTML 목업을 만들고 검토한다.
- 이유:
  - Review는 단순 좌우 비교가 아니라 기존 wiki 유사도 목록, 선택 개념 내용, 신규 개념 batch 카드가 함께 작동해야 한다.
- 결과:
  - Build handoff 전 목업 검토/승인 상태를 문서화해야 한다.

## ADR-007: LLM 후보 검토 신호는 review_route로 통합

- 상태: Accepted
- 결정: LLM 후보 출력에서는 `review_state`/`needs_human_review`를 분리하지 않고 `review_route`로 통합한다.
- 이유:
  - 20B 이하 작은 모델이 검토 흐름을 놓치지 않게 표현력을 제공한다.
  - 사람의 최종 결정과 LLM의 후보 라우팅 신호를 분리한다.
- 결과:
  - 사람 결정은 `human_decision`에 기록한다.
  - `retry_instruction`은 runner/human 메타로 별도 저장한다.
  - retry 후 이전 후보는 `superseded`로 표시하고 새 후보와 연결한다.


## ADR-008: Settings 파일 형식은 YAML

- 상태: Accepted
- 결정: 사용자 설정 파일은 YAML을 기본 형식으로 둔다.
- 이유:
  - 사람이 직접 읽고 수정하기 쉽다.
  - nested 설정(model, prompt, route, path)을 표현하기 좋다.
- 결과:
  - sample settings는 YAML 기준으로 작성한다.
  - `.env`는 secret/password/endpoint override 중심으로 사용한다.

## ADR-009: Sync는 기본 dry-run, 반영은 --apply

- 상태: Accepted
- 결정: `wiki sync`는 기본적으로 dry-run/report만 수행하고, 실제 반영은 `--apply`를 명시해야 한다.
- 이유:
  - Vault와 DB 동기화는 데이터 손상 위험이 있으므로 보수적이어야 한다.
- 결과:
  - `wiki sync` 기본 실행은 read-only다.
  - `wiki sync --apply`는 반영 결과와 artifact를 남긴다.

## ADR-010: Web Auth는 .env 사용자 비밀번호 기반

- 상태: Accepted
- 결정: 단일 관리자 Web UI 인증은 `.env`에 둔 사용자 비밀번호 기반으로 시작한다.
- 이유:
  - 단일 사용자 로컬 서버에 충분히 단순하다.
  - 복잡한 다중 사용자 권한은 범위 밖이다.
- 결과:
  - sample env에 Web admin user/password 관련 key를 문서화한다.
  - 실제 secret은 commit하지 않는다.

## ADR-011: Prompt log는 버전별 전체 저장 + change note

- 상태: Accepted
- 결정: prompt 변경 로그는 diff만 저장하지 않고 버전별 전체 prompt와 change note를 저장한다.
- 이유:
  - LLM 결과 재현성을 높인다.
  - 작은 변경도 실행 결과에 영향을 줄 수 있어 전체 prompt snapshot이 필요하다.
- 결과:
  - prompt test version, confirmed version, change note, created_at, created_by를 기록한다.

## ADR-012: Embedding 재인덱싱 정책

- 상태: Accepted
- 결정: 신규 wiki 확정 시 해당 항목은 즉시 embedding/index에 추가한다. 사용자는 필요 시 선택 항목 또는 전체 재인덱싱을 실행할 수 있다.
- 이유:
  - 신규 확정 지식은 검색 가능해야 한다.
  - 모델 변경 또는 dimension 변경 시 선택/전체 재인덱싱이 필요하다.
- 결과:
  - `wiki embed` 또는 별도 reindex 명령/옵션은 선택 항목과 전체를 지원해야 한다.
  - 재인덱싱은 validation required에 포함한다.

## ADR-013: Normalized format은 Markdown, MDX는 optional preview/export

- 상태: Accepted
- 결정: 비-Markdown 변환의 정본 normalized format은 Markdown으로 유지한다. MDX는 필요 시 Web preview/export용 optional format으로 둔다.
- 이유:
  - Obsidian 호환성이 핵심이다.
  - LLM 입력에는 MDX의 JSX/컴포넌트가 노이즈가 될 수 있다.
  - LLM에는 구조화된 Markdown + YAML frontmatter + artifact JSON이 더 단순하고 안전하다.
- 결과:
  - PDF/Office/HTML/URL 변환은 Markdown normalized file 생성을 우선한다.
  - MDX 생성은 2차 이후 Web preview/export 옵션으로 설계한다.


## ADR-014: Web UI 기술스택 확정

- 상태: Accepted
- 결정: Phase 3 Web UI는 Python 기반 FastAPI + server-rendered HTML + Vanilla JS로 완성한다.
- 확정 stack:
  - Web backend/API: `FastAPI`
  - ASGI server: `uvicorn`
  - Template: `Jinja2`
  - Form parsing: `python-multipart`
  - Settings YAML: `PyYAML`
  - Env loading: `python-dotenv`
  - Data validation/schema: `pydantic`
  - Frontend: server-rendered HTML + Vanilla JavaScript ES modules + plain CSS
  - Graph popup: inline SVG + Vanilla JS
  - Auth: `.env`의 관리자 비밀번호 + stdlib `hmac` 기반 signed session cookie
- 제외:
  - React/Vite/Next.js 같은 Node 기반 frontend build pipeline
  - Tailwind build pipeline
  - 외부 graph visualization library 필수 의존
  - 다중 사용자 권한/협업 auth
- 이유:
  - 프로젝트의 기본 언어가 Python이다.
  - CLI/API/Web이 같은 service/repository 계층을 공유하기 쉽다.
  - 단일 관리자 로컬 UI에 충분하다.
  - Node build chain 없이 Web UI를 완성할 수 있다.
- 결과:
  - Build agent는 위 dependency 추가를 승인된 것으로 간주한다.
  - 추가 dependency가 이 목록을 넘어가면 중단하고 사용자 승인을 요청한다.
  - Phase 3는 이 stack으로 Web UI 완성을 목표로 한다.
