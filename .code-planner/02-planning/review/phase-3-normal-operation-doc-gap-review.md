# Phase 3 Normal Operation — Document Gap Review

## 목적

이 문서는 현재 코드 구현 상태를 바로 고치기 위한 문서가 아니다.  
기존 Planning 문서들이 Phase 3 정상 운영을 충분히 정의하고 있는지 먼저 점검하고, 부족한 계획 항목을 재수립하기 위한 review 문서다.

## 검토 기준 문서

- Phase 문서: `.code-planner/02-planning/phases/phase-3-web-review-ui.md`
- Feature 계약: `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`
- Build handoff: `.code-planner/02-planning/handoff/build-handoff.md`
- UX 변경 계획: `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`
- Validation plan: `.code-planner/02-planning/validation/validation-plan.md`

## 결론

현재 문서들은 Phase 3의 화면 구조와 주요 UX는 비교적 구체적이지만, “정상 운영”에 필요한 backend effect, setup lifecycle, pipeline lifecycle, test semantics, evidence 기준은 충분히 고정되어 있지 않다.

따라서 정상 운영 계획서는 단순 버그 목록이 아니라 아래 5개 계약을 먼저 보강하는 방향이어야 한다.

1. Setup/Onboarding lifecycle 계약
2. Web API ↔ UI field contract
3. Inbox processing lifecycle 계약
4. Mapping decision effect 계약
5. Settings test semantics 계약

---

# 1. 문서별 부족 항목

## 1.1 Phase 문서 부족점

파일: `.code-planner/02-planning/phases/phase-3-web-review-ui.md`

현재 문서가 정의한 것:

- Dashboard, Mapping, Wiki graph, Settings의 사용자 결과
- PC/Mobile navigation 및 Mapping CTA
- Web 기술스택

부족한 것:

- 신규/미설정 사용자 진입 규칙이 없음
- Onboarding 완료 조건과 완료 후 nav 처리 규칙이 없음
- Mapping 버튼이 실제 DB/Vault/index에 어떤 효과를 내야 하는지 없음
- Inbox process가 실제 pipeline을 호출해야 하는지, queued artifact만 허용되는지 없음
- Settings의 test run이 실제 LLM call인지 schema dry-run인지 정의가 약함

필요 보강:

- Phase 3 purpose에 “정상 운영 lifecycle” 포함
- Exit criteria에 setup 완료, pipeline 실행, mapping 반영 evidence 포함

## 1.2 Feature 계약 부족점

파일: `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`

현재 문서가 정의한 것:

- 주요 사용자 흐름
- Mapping 화면 구조
- Settings prompt/model 관리

부족한 것:

- Login 이후 first-run routing이 정의되지 않음
- “병합/신규/수정”이 UI action인지 실제 write operation인지 불명확
- `Edit`의 의미가 후보 payload 수정인지 edit-needed decision인지 불명확
- Prompt test → confirm에서 test 실패 시 confirm 금지 조건은 일부 문서에 있으나 feature contract에서 충분히 강하지 않음
- Search/Ask, Vault Browser는 Phase 3 범위에 들어왔으나 feature contract의 정상 운영 조건이 부족함

필요 보강:

- Feature contract에 action effect table 추가
- Settings test state: `passed | failed | blocked` 추가
- Search/Ask 미설정 상태 처리 추가

## 1.3 Build handoff 부족점

파일: `.code-planner/02-planning/handoff/build-handoff.md`

현재 문서가 정의한 것:

- Phase 3 최신 UX 및 정상 운영 gap plan 참조
- 기존 CLI/LLM schema 개요

부족한 것:

- Build가 어떤 gap을 먼저 구현해야 하는지 “정상 운영 기준”의 우선순위가 handoff 본문에 약함
- backend contract를 바꿔도 되는 범위가 구체적이지 않음
- evidence 필수 제출 형식이 Phase 3 정상 운영 관점에서 부족함

필요 보강:

- 정상 운영 gap plan을 Phase 3 Build의 필수 입력으로 승격
- API/schema 변경 필요 시 문서 갱신/승인 조건 명시
- evidence path와 pass/fail 기준 명시

## 1.4 UX 변경 계획 부족점

파일: `.code-planner/02-planning/handoff/phase-3-ux-change-plan.md`

현재 문서가 정의한 것:

- mobile side drawer
- Mapping existing wiki action
- PC/Mobile CTA 위치

부족한 것:

- 의도적으로 UX 변경 건만 다루므로 backend effect가 제외되어 있음
- 이후 정상 운영 계획과 역할 분리가 필요함

필요 보강:

- 이 문서는 유지하되, 정상 운영 계획서에서 “UX 변경은 완료/별도, backend effect는 정상 운영 계획에서 처리”로 분리

## 1.5 Validation plan 부족점

파일: `.code-planner/02-planning/validation/validation-plan.md`

현재 문서가 정의한 것:

- Mockup/UX match
- Onboarding, Inbox, Mapping, Settings 정상 운영 readiness 일부 추가

부족한 것:

- 각 정상 운영 gap의 evidence 형태가 구체적이지 않음
- 자동 검증과 수동 검증이 분리되어 있지 않음
- `pass | fail | blocked` 기준이 Phase 3 정상 운영 항목별로 부족함

필요 보강:

- 정상 운영 항목별 evidence path 추가
- fresh workspace 시나리오, ingest-to-mapping 시나리오, settings test 시나리오를 validation goal로 승격

---

# 2. 문서 기준으로 재수립해야 할 계획 구조

기존 점검 결과는 참고 자료로만 사용하고, 계획서는 아래 순서로 다시 구성한다.

1. 정상 운영 scope 재정의
   - UX 변경 완료분과 backend 정상 운영 gap 분리
2. 문서 계약 보강 항목
   - Phase/Feature/Handoff/Validation에 반영할 결정
3. Build 작업 단위
   - Setup lifecycle
   - API/UI field contract
   - Inbox pipeline
   - Mapping decision effect
   - Settings test semantics
   - Dashboard/Search/Ask/Vault status quality
4. 검증 시나리오
   - Fresh start
   - Onboarding completion
   - Ingest to Mapping
   - Mapping write effect
   - Settings test and prompt confirm
5. Evidence 기준
   - JSON/API response
   - DB row
   - Vault file diff/result
   - index/search result
   - screenshot/manual observation

---

# 3. 사용자 확인이 필요한 결정

정상 운영 계획을 Build-ready로 만들기 전에 아래 결정이 필요하다.

1. Onboarding 완료 기준
   - A. 설정값 저장만으로 완료
   - B. connection test까지 성공해야 완료
   - 권장: B, 단 로컬 LLM이 꺼져 있으면 `blocked` 상태로 명확히 표시

2. Inbox process 방식
   - A. Web에서 즉시 pipeline 실행
   - B. Web에서 job queue 생성, runner가 처리
   - 권장: B, 단 runner 미동작 상태가 사용자에게 보여야 함

3. Mapping write 방식
   - A. Add/Merge/Create 즉시 Vault/DB/index 반영
   - B. preview 생성 후 Confirm에서 반영
   - 권장: B, 실수 방지와 evidence 확보에 유리

4. Prompt test 방식
   - A. 실제 LLM call 필수
   - B. schema/sample dry-run도 통과로 인정
   - 권장: `passed | failed | blocked` 3상태. LLM 미설정이면 blocked.

---

# 4. 재작성 대상 문서

- `.code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md`
- 필요 시 이후 보강:
  - `.code-planner/02-planning/phases/phase-3-web-review-ui.md`
  - `.code-planner/02-planning/features/feature-phase3-web-review-ui.md`
  - `.code-planner/02-planning/validation/validation-plan.md`

## 현재 상태

- Review status: `documents_inspected`
- Next action: 정상 운영 계획서를 문서 기준 구조로 재작성
