# Phase 3 Web UI Gap Review and Fix Plan Addendum

## 목적

`/fix phase-3`로 바로 들어가기 전에, 현재 Web UI가 Phase 3 목표 대비 어디까지 구현되었고 무엇이 부족한지 사용자 관점으로 재정리한다.

이 문서는 기존 fix request의 보강 계획이다.

- 기존 fix request: `.code-planner/04-check/fix-requests/phase-3-fix-request.md`
- check report: `.code-planner/04-check/phase-3-check-report.md`

## 사용자 재확인 피드백

- 현재 보이는 메뉴는 `Dashboard / Review / Settings / Logout` 수준이다.
- 첫 화면에서 onboarding/setup 안내가 없다.
- Wiki 조회 화면이 없다.
- Mapping을 별도 작업 흐름으로 이해하고 처리할 수 없다.
- Dashboard 버튼과 세부 상태가 실제 작업으로 연결되지 않는다.
- Settings는 prompt 중심이며 model 설정/상태 확인이 충분하지 않다.

## 현재 구현 인벤토리

### 있는 것

- FastAPI app 및 `wiki web` 실행 경로.
- `.env` 기반 admin password 로그인.
- 기본 navigation: Dashboard, Review, Settings, Logout.
- Dashboard metric API 일부.
- Review 3-column template 형태.
- pending candidate 조회와 human decision/retry instruction API 일부.
- Prompt version create/confirm API 일부.
- Graph popup 형태.

### 실제 사용 관점에서 부족한 것

- 첫 사용자가 “다음에 무엇을 해야 하는지” 알 수 있는 onboarding/setup 없음.
- Wiki를 읽고 찾는 독립 화면 없음.
- Mapping 후보를 중심으로 검토하는 명확한 화면/필터/상태 없음.
- Review의 왼쪽 목록은 진짜 “유사도 목록”이 아니라 concept 파일 목록에 가까움.
- Dashboard action button은 실제 동작 또는 명확한 read-only report가 아님.
- Graph popup은 후보 node 클릭 시 후보 payload를 보여주지 못할 수 있음.
- Settings에서 model route/config 상태, missing env, test run 결과가 충분히 보이지 않음.
- Empty-state가 부족해 데이터가 없으면 “기능이 없는 화면”처럼 보임.

## 목표 대비 구현율 재평가

| 영역 | 목표 | 현재 상태 | 구현율 |
|---|---|---|---:|
| Login/Auth | `.env` 비밀번호 기반 로그인 | 동작 | 80% |
| Onboarding/Setup | 첫 화면 안내/상태 점검 | 없음 | 0% |
| Dashboard | 처리 현황/오류/pending/wiki/system + 작업 진입 | 기본 카드만 있고 세부 기능 부족 | 35% |
| Wiki 조회 | wiki 목록/검색/상세 조회 | 독립 화면 없음 | 0–10% |
| Review Main | 기존 wiki 유사도/선택 개념/신규 batch | 형태는 있으나 workflow 부족 | 35% |
| Mapping | mapping 후보 검토/병합/신규 판단 | 1급 UI 없음 | 10–20% |
| Graph popup | 1-hop graph + wiki 내용 | 기본 형태만 있음 | 40% |
| Settings | model/prompt/test/confirm/change log | prompt 일부만 있음 | 40% |
| Evidence/Test | 사용자 기능 검증 | smoke 위주로 과대평가 | 30% |

전체 체감 구현율: **35–45%**.

## `/fix phase-3`의 보강 목표

## Subagent cross-check result

- Result: **issues_found**
- Verdict: 현재 Phase 3 fix target은 “무엇이 빠졌다”는 목록은 있으나, `/fix`가 바로 구현하기에는 화면 IA, layout, Settings 실기능 범위가 부족하다.
- Suggested readiness: `/fix phase-3` 진입 전 아래 design baseline과 pending decisions를 확정해야 한다.

## User decisions added after cross-check

- Settings에서 Web으로 직접 변경 가능한 범위:
  - Prompt 설정/버전 관리
  - LLM 설정
  - Vault 폴더 변경은 Onboarding/Setup 흐름에서 처리
- 첫 접속 흐름:
  - 최초 접속 시 Onboarding으로 진입
  - Onboarding에서 `.env` setup 상태를 안내
- 화면 구조:
  - 사용자 선택: **3안 — A안 기반 + Settings만 B안식 좌측 탭 구조**.
  - 비교 문서: `.code-planner/04-check/fix-requests/phase-3-web-ui-ab-wireframes.md`

핵심 누락:

1. PC-first 디자인 원칙이 문서에 명시되지 않음.
2. Mobile은 “최적화 제외”가 아니라 “보조 접근에서 무엇까지 보장할지”가 정의되어야 함.
3. Navigation/IA 기준선이 메뉴 이름 수준에 머물러 있고 각 화면 책임이 불명확함.
4. Settings가 read-only인지, prompt만 변경 가능한지, model route까지 변경 가능한지 미정.
5. 로그인 직후 landing/onboarding 정책이 없음.
6. Dashboard 버튼이 실제 실행, read-only report, CLI 안내 중 무엇인지 미정.
7. 검증 evidence에 PC viewport와 mobile-secondary 체크가 분리되어 있지 않음.

## Design baseline to apply before `/fix`

### PC-first / mobile-secondary 원칙

- Phase 3 Web UI는 **PC-first**로 설계한다.
- Primary viewport: desktop browser, 최소 1280px 이상, 권장 1440–1920px.
- 주요 작업인 Review/Mapping batch 처리, Settings 편집, Graph 확인은 PC 화면을 기준으로 한다.
- Mobile은 **보조 접근(sub-access)**이다.
  - 모바일에서 필수 보장: login, Dashboard 상태 조회, Wiki 읽기.
  - 모바일에서 필수 아님: 복잡한 Review/Mapping batch 작업, Settings 편집, Graph popup 정밀 조작.

### Information Architecture baseline

상단 메뉴는 다음 순서와 책임을 기본안으로 한다.

```text
Onboarding | Dashboard | Wiki | Review / Mapping | Settings | Logout
```

화면 책임:

- `Onboarding`: 첫 실행/빈 데이터/설정 누락 상태에서 다음 작업을 안내한다.
- `Dashboard`: 전체 상태 요약과 read-only 운영 report를 보여준다.
- `Wiki`: 확정/생성된 wiki 내용을 검색·조회한다.
- `Review / Mapping`: LLM 후보, mapping 후보, 신규 개념 batch를 검토·처리한다.
- `Settings`: model 상태/route와 prompt versioning/test/confirm을 관리한다.

### Screen catalog baseline

`/fix`에서 최소 아래 route/screen을 목표로 한다.

| Route | Screen | 책임 |
|---|---|---|
| `/login` | Login | `.env` admin password 로그인 |
| `/onboarding` or `/setup` | Onboarding | 초기 상태, 설정 누락, 다음 액션 안내 |
| `/dashboard` | Dashboard | 처리 현황, pending/error/review/wiki/system status |
| `/wiki` | Wiki browse | wiki 목록/검색/master-detail 조회 |
| `/review` | Review / Mapping | 후보 batch, mapping, merge/new/edit/retry 처리 |
| `/settings` | Settings | model 상태, prompt test→confirm, change log |

### Layout baseline

- Global: sticky top navigation + page title/hint + action toolbar 패턴.
- Dashboard: card grid + detail report panels.
- Wiki: PC에서는 master-detail 2-column.
- Review/Mapping: PC에서는 3-column 고정.
  - left: existing wiki/mapping target list, 약 300–360px
  - center: selected wiki/concept detail, fluid
  - right: candidate batch cards, 약 360px
- Settings: PC에서는 section/tabs 또는 2-column layout.
  - 확정: Settings 내부는 B안식 좌측 탭 구조를 사용한다.
  - Left tabs: LLM, Prompt, Vault, Auth.
  - Right panel: 선택한 설정 영역의 상태/입력/결과를 표시한다.
  - Model status/route/edit panel
  - Prompt versioning/test/confirm/history panel
- Mobile: 1-column collapse, read-only 접근 중심.

### Empty-state standard

모든 주요 화면/panel은 비어 있을 때 아래 3가지를 보여야 한다.

1. 왜 비어 있는지 한 줄 설명.
2. 다음에 할 일: CLI 명령 또는 이동할 화면.
3. primary CTA: Onboarding, Wiki, Review/Mapping 등 관련 화면 링크.

### Settings functional baseline

Settings는 “보기만 있는 빈 화면”이 아니어야 한다. 최소 다음을 제공한다.

- Model status:
  - configured models
  - route mapping
  - endpoint/model/key configured/missing 여부
  - secret value masking
- Prompt versioning:
  - confirmed/test version 표시
  - test version 저장
  - test run 결과 또는 artifact 표시
  - confirmed version 승격
  - change log/history
- Auth/env:
  - Web admin password configured 여부만 표시, 값은 절대 노출 금지.

### Dashboard button policy

- 동작하지 않는 placeholder 버튼은 금지한다.
- Web에서 안전한 read-only report로 연결할 수 있으면 활성화한다.
- destructive/apply 동작은 Web에서 직접 실행하지 않는다.
- Web에서 실행하지 않는 기능은 disabled + 이유 + CLI 안내로 표시한다.

### Graph behavior

- 선택 concept 중심 1-hop만 표시한다.
- concept markdown이 없는 candidate node를 클릭해도 404로 끝나지 않고 candidate payload/detail을 보여준다.

### Verification evidence baseline

`/check phase-3` evidence에는 아래가 포함되어야 한다.

- PC manual checklist: 1920 / 1440 / 1280px.
- Mobile-secondary checklist: 360 / 768px에서 login, Dashboard, Wiki 읽기 확인.
- Seeded functional tests:
  - Wiki browse/detail
  - Review/Mapping 후보 batch
  - reject + retry instruction
  - prompt test → confirm
  - graph candidate node detail
- Tailnet manual user confirmation.

### 1. Navigation 재정의

상단 메뉴는 최소 다음을 보여야 한다.

```text
Onboarding | Dashboard | Wiki | Review / Mapping | Settings | Logout
```

조건:

- 첫 실행/빈 데이터 상태에서는 Onboarding 또는 Setup card가 Dashboard 첫 영역에 노출되어야 한다.
- Review와 Mapping이 같은 화면이면 메뉴 label에서 `Review / Mapping`처럼 명확히 표현한다.
- Wiki 조회는 Review에 묻히지 않고 별도 화면으로 접근 가능해야 한다.

### 2. Onboarding/Setup 화면 추가

필수 표시:

- workspace initialized 여부
- DB/schema 상태
- `.env` web admin password 설정 여부
- LLM endpoint/model/key 설정 여부는 값 노출 없이 configured/missing만 표시
- wiki concept 수
- review candidate 수
- failed/pending job 수
- 다음 액션 안내:
  - 샘플/자료가 없으면 CLI ingest/normalize/chunk/extract 흐름 안내
  - 후보가 있으면 Review / Mapping으로 이동
  - wiki가 있으면 Wiki로 이동

### 3. Wiki 화면 추가

필수 기능:

- `/wiki` page.
- wiki/concept/page 목록.
- 검색/filter.
- 선택한 wiki markdown 내용 preview.
- aliases/claims/relations 추출 표시. DB에 구조화 데이터가 없으면 markdown section 기반 fallback 허용.
- source/path 표시.

### 4. Dashboard를 실제 상태 중심으로 강화

필수 패널:

- 처리 현황: source pipeline stage별 count.
- 승인 필요: pending review candidates count/type/route breakdown.
- Pending job: queued/running/needs_review count + 최근 job 목록.
- 오류: failed job 목록과 error 요약.
- Wiki 개수: concept/page/source counts.
- 시스템 상태: DB/schema/env/model config status.

버튼 정책:

- 동작하지 않는 버튼은 제거하거나 disabled + 이유 표시.
- 실제 read-only report로 연결 가능한 버튼만 활성화.
- destructive/apply 동작은 Web에서 바로 실행하지 않는다.

### 5. Review / Mapping workflow 강화

필수 구조:

- 왼쪽: 기존 wiki 후보 목록. mapping/similarity 데이터가 있으면 similarity/order를 사용한다.
- 가운데: 선택 wiki 상세 + aliases/claims/relations + compile preview.
- 오른쪽: 신규/Mapping 후보 batch cards.

후보 카드 필수 정보:

- candidate_type
- candidate_key
- review_route
- review_reason
- mapping_action
- confidence
- source/evidence refs
- related_candidate_keys

필수 action:

- merge
- create_new
- edit
- reject + retry instruction
- batch selection + confirmation

상태 표시:

- action 후 status가 즉시 화면에 반영되어야 한다.
- empty-state에서 후보 생성 경로를 안내해야 한다.

### 6. Graph popup 보강

필수 기능:

- 선택 concept 중심 1-hop 표시.
- 후보 node 클릭 시 concept markdown이 없어도 candidate payload/detail을 보여준다.
- 과도한 전체 graph 확장은 금지한다.

### 7. Settings 보강

필수 영역:

- Model settings/status:
  - configured models
  - route mapping
  - missing endpoint/key/model warning
  - sensitive value masking
- Prompt versioning:
  - confirmed/test versions
  - change note
  - save test version
  - test run result/artifact
  - confirm version
  - history/change log

수정 가능 여부:

- Web에서 model 설정 변경까지 할지, read-only + CLI 안내로 둘지는 `/fix` 시작 전에 결정해도 된다.
- 단, 현재 Phase 3 pass 기준에는 “model 설정을 볼 수 있다”가 포함되므로 최소 read-only 상태 확인은 필수다.

## Acceptance criteria for recheck

`/fix phase-3` 이후 `/check phase-3`는 아래를 모두 확인해야 한다.

1. Tailnet에서 로그인 후 첫 화면에 onboarding/setup 안내 또는 상태 card가 보인다.
2. 상단 메뉴에 Wiki와 Review/Mapping이 명확히 보인다.
3. Wiki 화면에서 실제 markdown wiki/concept를 조회할 수 있다.
4. Dashboard가 placeholder 버튼이 아니라 실제 상태/보고를 보여준다.
5. Review/Mapping 화면에서 seeded mapping/node/relation 후보를 보고 처리할 수 있다.
6. reject + retry instruction이 DB 상태로 저장되고 화면에서 반영된다.
7. Graph popup에서 concept node와 candidate node 모두 내용 패널을 보여준다.
8. Settings에서 model route/config 상태와 prompt test→confirm 흐름을 확인할 수 있다.
9. Empty-state가 “기능 없음”이 아니라 “다음에 할 일”을 안내한다.
10. Evidence는 TestClient smoke뿐 아니라 Tailnet 수동 확인 결과를 포함한다.

## Suggested fix work units

1. `build-core-dev`
   - onboarding status API
   - wiki list/detail/search API
   - dashboard detail APIs
   - review/mapping read model API
   - graph candidate detail fallback

2. `build-ui-dev`
   - navigation rebuild
   - onboarding page/card
   - wiki page
   - dashboard detail panels
   - review/mapping cards and empty-state
   - settings model panel

3. `build-test-validation`
   - seeded functional tests
   - Tailnet manual checklist evidence
   - update phase-3 build evidence from ready=false to ready=true only after user confirmation
