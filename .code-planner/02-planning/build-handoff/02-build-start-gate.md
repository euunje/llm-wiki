# 02 Build Start Gate — LLM Wiki Local

## Gate result

- Gate status: ready
- Build 시작 가능 여부: 가능
- 시작 phase: Phase 1 — CLI Foundation

## 필수 입력 파일 확인

- [x] `.code-planner/01-ideation-approved.json`
- [x] `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- [x] `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- [x] `.code-planner/02-planning/phases/01-phase-plan.md`
- [x] `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- [x] `.code-planner/02-planning/validation/01-validation-plan.md`

## Build 시작 규칙

1. 대화 기억이 아니라 `.code-planner/02-planning/**` 문서를 기준으로 구현한다.
2. Phase 1부터 시작한다.
3. secrets 또는 실제 `.env` 값은 생성/커밋하지 않는다. sample env만 만든다.
4. Git commit/push는 사용자가 별도 요청할 때만 수행한다.
5. Build 중 schema/contract 변경이 필요하면 먼저 planning 문서와 차이를 보고한다.

## Phase 1 완료 게이트

Phase 1은 다음 E2E가 통과해야 완료로 본다.

```text
wiki init
  -> wiki ingest samples/*.md
  -> wiki normalize <source_id>
  -> wiki chunk <source_id>
  -> wiki embed source:<source_id>
  -> wiki models test <model_id>
  -> wiki extract-claims <source_id> --json
  -> wiki sync
```

## Build 전 모호성 처리

Planning에서 아래 초안을 제공했다.

- SQLite schema 초안: `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- LLM 후보 JSON schema 초안: `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- CLI E2E 테스트 플랜: `.code-planner/02-planning/validation/cli-e2e-test-plan.md`

Build agent는 위 초안을 기준으로 구현하되, 실제 라이브러리 제약 때문에 조정이 필요하면 변경 이유를 기록한다.


## UI/UX Build Gate Compatibility

- Canonical mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`
- Build gate compatibility mockup: `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- Canonical approval: `.code-planner/02-planning/review/phase-3-prv-feedback.md`
- Build gate compatibility approval: `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`
- 실제 리뷰는 PRV로 승인되었으며, legacy Lavish 파일명은 Build gate 호환용이다.


## Phase 3 Web UI 확정 기술스택

Build agent는 Phase 3 Web UI를 다음 stack으로 구현한다.

- FastAPI
- uvicorn
- Jinja2
- python-multipart
- pydantic
- PyYAML
- python-dotenv
- server-rendered HTML
- Vanilla JavaScript ES modules
- plain CSS
- inline SVG graph popup
- `.env` 관리자 비밀번호 + stdlib hmac signed session cookie

제외:

- React/Vite/Next.js
- Tailwind build pipeline
- 외부 graph visualization library 필수 의존
- 다중 사용자 auth

Dependency 승인 범위:

- 위 dependency는 Planning에서 승인된 것으로 간주한다.
- 이 목록 밖의 dependency가 필요하면 Build를 중단하고 사용자 승인을 요청한다.
