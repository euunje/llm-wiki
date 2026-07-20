# Phase 3 Normal Operation Plan — Document-Based Revision

## 목적

이 문서는 Phase 3 Web UI를 정상 운영 가능한 상태로 만들기 위한 계획서다.  
이전 UX 변경 계획서가 화면/상호작용을 다뤘다면, 이 문서는 기존 Planning 문서 기준으로 부족한 **운영 계약**을 보강한다.

이 계획서는 코드 점검 결과를 참고하되, 기준은 다음 문서다.

- `.code-planner/02-planning/phases/phase-3-web-review-ui.md`
- `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`
- `.code-planner/02-planning/handoff/build-handoff.md`
- `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`
- `.code-planner/02-planning/validation/validation-plan.md`
- 문서 gap review: `.code-planner/02-planning/review/phase-3-normal-operation-doc-gap-review.md`

## 범위 구분

### 이미 UX 기준으로 확인된 항목

- mobile side drawer navigation
- Mapping existing wiki action UI
- Search/Ask 내부 submenu
- Vault 2단 file tree + viewer

### 이 문서의 범위

- UX가 약속한 행동이 backend/DB/Vault/index에 실제로 연결되는지
- 신규 사용자 setup lifecycle이 정상 운영 흐름을 강제하는지
- test/confirm/process/action이 fake success나 placeholder가 아닌지
- 운영 테스트에서 evidence로 증명 가능한지

### 제외

- Phase 3 전체 UI 재설계
- 다중 사용자 권한
- 협업 approval workflow
- Vault 전체 직접 편집기
- 신규 프론트엔드 프레임워크 도입

---

# 1. 정상 운영 계약

Phase 3 정상 운영은 아래 6개 계약이 모두 충족되어야 한다.

## Contract A. Setup / Onboarding Lifecycle

신규 또는 설정 미완료 사용자는 Onboarding부터 시작해야 한다.

필수 계약:

- 로그인 후 setup 미완료 상태면 `/onboarding`으로 이동한다.
- setup 완료 상태면 Dashboard로 이동한다.
- setup 완료 후 top nav와 mobile drawer에서 Onboarding은 숨긴다.
- 재설정은 Settings에서 수행한다.
- setup 상태는 대화 기억이 아니라 settings/API response로 재현 가능해야 한다.

완료 기준:

- [ ] fresh workspace에서 로그인 후 Onboarding 진입
- [ ] 완료 후 Dashboard 진입
- [ ] 완료 후 Onboarding nav/drawer hidden
- [ ] Settings에서 LLM/Vault 재설정 가능

## Contract B. Web API ↔ UI Field Contract

UI가 읽는 field와 backend가 반환하는 field는 문서화되고 테스트 가능해야 한다.

필수 계약:

- `/api/setup/status`는 Onboarding checklist에 필요한 field를 모두 반환한다.
- Dashboard API는 Dashboard card와 Needs attention에 필요한 field를 반환한다.
- Settings LLM/Prompt API는 test 결과 상태를 일관된 enum으로 반환한다.
- field가 없어서 UI가 임의 fallback으로 성공/실패처럼 보이면 안 된다.

권장 상태 enum:

```text
ready | missing_config | running | passed | failed | blocked
```

완료 기준:

- [ ] Onboarding checklist false failure 없음
- [ ] Dashboard card 값이 실제 API field와 일치
- [ ] Settings test 결과가 실제 backend result와 일치
- [ ] API/UI contract test 존재

## Contract C. Inbox Processing Lifecycle

Inbox에서 자료를 추가하면 실제 처리 lifecycle이 시작되어야 한다.

필수 계약:

- Web upload/text/scan은 Source 또는 Inbox item으로 저장된다.
- Process action은 실제 job 또는 runner queue를 만든다.
- job 상태는 `new → queued → processing → needs_mapping | completed | failed` 중 하나로 이동한다.
- placeholder queue만 만들고 끝나는 것은 정상 운영이 아니다.
- 실패 시 error artifact와 retry path가 있어야 한다.

완료 기준:

- [ ] 브라우저 upload 성공
- [ ] process 후 job/artifact 생성
- [ ] 처리 상태가 화면에 반영
- [ ] 실패/retry evidence 존재

## Contract D. Mapping Decision Effect

Mapping action은 단순 UI label이 아니라 실제 system effect를 가져야 한다.

필수 계약:

| Action | 정상 운영 effect |
|---|---|
| Add to selected wiki | 기존 wiki에 alias/claim/relation 등 후보 값을 추가하는 변경안 생성 또는 적용 |
| Merge into selected wiki | 후보 concept를 기존 concept와 병합하는 결정 저장 및 preview/result 반영 |
| Create new | 새 wiki page/DB concept 생성 또는 생성 preview 후 confirm 적용 |
| Edit | 후보 수정 내용 또는 수정 요청을 저장하고 이후 confirm 경로에 반영 |
| Reject + Retry | reject reason + retry instruction 저장, retry 후보 생성 경로 연결 |
| Confirm mapping | 해당 step/후보의 최종 반영 상태를 확정 |

Vault 반영 정책은 다음 중 하나로 고정해야 한다.

- `preview_then_confirm` 권장: preview 생성 후 Confirm에서 DB/Vault/index 반영
- `immediate_apply`: action 클릭 즉시 반영, undo/rollback evidence 필요

완료 기준:

- [ ] action별 DB decision row 존재
- [ ] 필요한 경우 Vault Markdown 생성/변경 확인
- [ ] create/merge 후 embedding/index 갱신 또는 queued 상태 확인
- [ ] action 결과가 Mapping/Wiki/Search에서 재조회 가능

## Contract E. Settings Test Semantics

Settings의 test는 실제 의미 있는 검증이어야 한다.

추가 확인 — Phase 2 기본 프롬프트 반영 상태:

- Phase 2 기본 프롬프트는 `src/llm_wiki/schema/prompts.py`의 `DEFAULT_PROMPTS`에 정의되어 있다.
- workspace 초기화 시 `ensure_default_prompts()`가 task별 confirmed version을 DB `prompt_versions`에 seed한다.
- 기본 version label은 `phase2-default-v1`이다.
- `extract_claims` 실행 경로는 `get_active_prompt(..., "extract_claims")`를 호출하고, 해당 `prompt_version_id`를 `agent_runs` 및 artifact payload에 기록한다.
- `summarize` 실행 경로도 active prompt id를 artifact payload에 기록한다.
- Web Settings API는 active prompt와 Phase 2 default 여부를 표시하고 rollback copy를 만들 수 있다.
- 단, 현재 확인 기준으로 `map`, `link`, `compile`, `ask`의 placeholder 실행 경로는 active prompt를 system prompt로 실제 사용하거나 prompt id를 일관되게 기록하는 수준이 충분하지 않다.
- Web prompt `test`/`confirm`은 현재 test version 생성 및 `prompt_confirm_test` artifact 기록 중심이며, schema validation/sample dry-run/lightweight LLM call과 failed/blocked confirm guard는 보강 대상이다.

필수 계약:

- LLM connection test는 provider endpoint/API key/model 연결을 실제 확인한다.
- Prompt test는 schema validation, sample dry-run, lightweight LLM call 중 하나 이상을 수행한다.
- test 결과는 `passed | failed | blocked`로 기록한다.
- failed/blocked 상태에서는 confirm을 허용하지 않는다.
- Phase 2 기본 프롬프트 또는 사용자가 confirm한 active prompt는 관련 task runner에서 실제 system prompt/input prompt로 사용되어야 한다.
- AgentRun/artifact에는 사용된 `prompt_version_id`와 test evidence가 남아야 한다.

완료 기준:

- [ ] 정상 endpoint 성공
- [ ] 잘못된 endpoint 실패 사유 표시
- [ ] LLM 미설정이면 blocked 표시
- [ ] prompt test evidence 저장
- [ ] failed test confirm 불가

## Contract F. Operational State Visibility

오류/빈 상태/미설정 상태는 사용자가 구분할 수 있어야 한다.

필수 계약:

- Dashboard는 LLM/Vault/DB/job/index 상태를 보여준다.
- Mapping 후보 없음은 “자료 없음”, “처리 전”, “설정 미완료”를 구분한다.
- Search/Ask는 index 없음, LLM 미설정, 검색 결과 없음, 답변 실패를 구분한다.
- Vault는 read-only 상태와 경로 오류를 구분한다.

완료 기준:

- [ ] 주요 empty/error/success state가 별도 message와 next action을 가진다.
- [ ] silent fallback 없음

---

# 2. 문서 보강 작업

Build 착수 전 또는 Build와 함께 다음 문서 보강이 필요하다.

## 2.1 Phase 문서 보강

대상: `.code-planner/02-planning/phases/phase-3-web-review-ui.md`

보강 항목:

- User-visible outcome에 Onboarding lifecycle 추가
- Exit criteria에 다음 추가
  - setup 미완료 → onboarding
  - Inbox process 실제 job/pipeline
  - Mapping action effect evidence
  - Settings test result evidence

## 2.2 Feature 계약 보강

대상: `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`

보강 항목:

- action effect table 추가
- first-run flow 추가
- Search/Ask와 Vault 정상 상태 계약 추가
- Settings test state enum 추가

## 2.3 Validation plan 보강

대상: `.code-planner/02-planning/validation/validation-plan.md`

보강 항목:

- Fresh start scenario
- Ingest to Mapping scenario
- Mapping write effect scenario
- Settings test/confirm scenario
- Evidence path 구체화

---

# 3. Build 작업 단위

## WU-01. Setup/Onboarding Lifecycle

목표:

- 신규/미설정 사용자를 Onboarding으로 유도하고, 완료 후 Onboarding nav를 숨긴다.

주요 작업:

- setup status contract 확정
- needs_onboarding 계산
- route gating
- onboarding_complete 저장 또는 계산 정책 구현
- base nav/drawer 조건부 렌더링

검증:

- fresh workspace login flow
- completed workspace login flow
- nav/drawer hidden 확인

## WU-02. API/UI Field Contract 정합화

목표:

- UI가 읽는 모든 운영 상태 field를 backend가 명시적으로 제공한다.

주요 작업:

- `/api/setup/status` 계약 고정
- dashboard metrics/status 계약 고정
- settings llm/prompt test response 계약 고정
- frontend fallback 제거 또는 명확한 blocked 처리

검증:

- API response snapshot
- UI checklist/card 상태 확인

## WU-03. Inbox Processing Lifecycle

목표:

- Inbox upload/text/scan에서 실제 처리 job으로 이어지는 운영 흐름을 만든다.

주요 작업:

- browser multipart upload 계약 정합화
- process action이 실제 CLI/service pipeline 또는 runner queue와 연결
- job status/result/error artifact 화면 반영
- retry path 연결

검증:

- Markdown 업로드 → process → artifact/job 생성
- 실패 sample → error artifact → retry

## WU-04. Mapping Decision Effect

목표:

- Mapping action이 DB/Vault/index에 실제 효과를 남긴다.

주요 작업:

- `preview_then_confirm` 또는 `immediate_apply` 중 정책 확정
- Add/Merge/Create/Edit/Reject/Confirm effect 구현
- Wiki compile preview와 실제 반영 상태 연결
- embedding/index update 또는 queued state 연결

검증:

- action별 DB row
- Vault Markdown 생성/변경
- Wiki/Search에서 결과 재조회

## WU-05. Settings Test Semantics

목표:

- connection test와 prompt test를 실제 검증으로 만든다.
- Phase 2 기본 프롬프트 및 confirmed prompt가 실제 실행 경로에서 일관되게 사용되도록 한다.

주요 작업:

- provider별 connection test
- provider/model selection 저장
- prompt test endpoint
- failed/blocked confirm guard
- task별 active prompt 사용 경로 정합화
  - `extract_claims`: 현재 active prompt 사용 및 `prompt_version_id` 기록 확인됨. 회귀 테스트 유지.
  - `summarize`: active prompt id 기록은 확인됨. 실제 prompt text 사용 여부는 Build에서 명확화.
  - `map`, `link`, `compile`, `ask`: active prompt 조회/사용/기록을 일관화.
- prompt test artifact에 validation type, status, sample input/output 또는 blocked reason 기록

검증:

- 정상/실패/blocked 3상태 테스트
- prompt confirm guard
- confirmed prompt 변경 후 다음 task 실행에서 새 `prompt_version_id`가 `agent_runs`/artifact에 반영되는지 확인

## WU-06. Operational State Visibility

목표:

- Dashboard/Mapping/Search/Ask/Vault에서 사용자가 현재 상태와 다음 행동을 알 수 있게 한다.

주요 작업:

- Dashboard Needs attention field 정합화
- Mapping empty state 분기
- Search/Ask LLM/index 상태 표시
- Vault path/read error 표시

검증:

- setup missing / no data / processing / success / failure 수동 및 API 검증

---

# 4. 권장 작업 순서

1. 문서 보강: Phase/Feature/Validation에 정상 운영 계약 반영
2. WU-01 Setup/Onboarding Lifecycle
3. WU-02 API/UI Field Contract
4. WU-03 Inbox Processing Lifecycle
5. WU-04 Mapping Decision Effect
6. WU-05 Settings Test Semantics
7. WU-06 Operational State Visibility
8. Fresh workspace 운영 유사 테스트
9. 전체 Phase 3 validation 재실행

---

# 5. 운영 유사 테스트 시나리오

## Scenario A. Fresh Workspace

1. 새 workspace 준비
2. Web 실행
3. 로그인
4. Onboarding 강제 진입
5. LLM/Vault/model 설정
6. 완료 후 Dashboard 진입
7. Onboarding nav hidden 확인

## Scenario B. Source to Mapping

1. Inbox에서 Markdown 업로드
2. Process 실행
3. 처리 job/artifact 확인
4. 후보 생성 후 Mapping 진입
5. Existing wiki match 선택
6. Add/Merge/Create/Reject 중 하나 실행
7. preview/result/evidence 확인

## Scenario C. Mapping to Wiki/Search

1. Confirm mapping
2. Vault Markdown/DB/index 반영 확인
3. Wiki에서 문서 확인
4. Search에서 결과 확인
5. Ask에서 evidence 포함 답변 확인

## Scenario D. Settings Test

1. LLM connection test success/fail/blocked 확인
2. Prompt test version 저장
3. Prompt test 실행
4. 실패 시 confirm 불가
5. 성공 시 confirm 및 history 기록
6. confirmed prompt를 바꾼 뒤 관련 task 실행
7. `agent_runs.prompt_version_id`와 artifact payload가 새 confirmed prompt id를 가리키는지 확인

---

# 6. Evidence 기준

Build 완료 시 다음 evidence가 필요하다.

- setup status before/after JSON
- route gating 확인 로그 또는 테스트 결과
- browser upload request/response evidence
- process job/artifact evidence
- mapping decision DB row
- Vault Markdown 생성/변경 evidence
- embedding/index update 또는 queued evidence
- prompt test result artifact
- search/ask result with evidence
- Phase 3 pytest 결과

Evidence path:

- `.code-planner/03-build/evidence/phase-3-normal-operation/`

---

# 7. 남은 사용자 결정

정상 운영 구현 전 다음 결정을 확정해야 한다.

1. Onboarding 완료 기준
   - 추천: connection test까지 성공해야 완료. 단 LLM이 꺼져 있으면 `blocked`로 표시.
2. Inbox process 방식
   - 추천: Web은 job queue 생성, runner/service가 처리. runner 미동작 상태는 Dashboard/Inbox에 표시.
3. Mapping write 정책
   - 추천: `preview_then_confirm`.
4. Prompt test 통과 기준
   - 추천: `passed | failed | blocked` 3상태. LLM 미설정은 blocked.

---

# 8. Build 지시 문구

```text
Phase 3 UX 변경은 별도 계획으로 확인되었다.
이제 .code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md 기준으로 정상 운영 계약을 구현한다.
먼저 Phase/Feature/Validation 문서의 부족 계약을 보강하고, 그 다음 WU-01부터 순서대로 구현한다.
placeholder success, fake queue, UI-only action은 정상 운영 완료로 인정하지 않는다.
각 작업은 API response, DB row, Vault file, index/search result, pytest/manual evidence로 검증한다.
```
