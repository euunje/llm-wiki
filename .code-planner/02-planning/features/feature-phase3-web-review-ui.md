# Feature Contract — Phase 3 Web Review UI

## Phase 목적

단일 관리자 사용자가 PC와 Mobile Web에서 처리 현황을 보고, LLM 후보를 검토하고, 병합/신규/retry/prompt 관리를 할 수 있게 한다.

## 주요 사용자 흐름

```text
로그인
  -> 대시보드에서 처리 현황 확인
  -> Mapping 화면 진입
  -> 신규 개념 batch 카드 확인
  -> 기존 wiki 유사도 목록 선택
  -> 가운데에서 기존 개념 의미 확인
  -> 3-step wizard에서 병합 또는 신규 처리
  -> 필요 시 reject reason + retry instruction
  -> 필요 시 Wiki compile preview 펼치기
  -> Settings에서 model/prompt/version 관리
```

## 포함 기능

### 1. Login

- 단일 관리자 기준
- 로컬 서버 중심
- 인증 방식은 planning에서 선택 필요

### 2. Dashboard

표시 항목:

- 자료 처리 현황
- 승인 필요
- pending 항목
- 오류
- wiki 개수
- 시스템 상태

### 3. Mapping Main Screen

PC 기본 구조:

```text
상단: Page 검증 → Page Mapping → Relationship 검증 → 오류/에러
좌측: Candidate queue       | 우측: 현재 step workspace
후보 목록/상태             | 의미/aliases/claims/relations, preview, actions
```

Mobile 기본 구조:

```text
상단: compact header + 사이드 메뉴 버튼(☰)
사이드 drawer: Mapping submenu/stepper
본문: Candidate 선택 → Existing wiki match 선택/전환 → 현재 step card → preview/details
하단 sticky CTA: Add to selected wiki / Merge into selected wiki / Create new / Reject + Retry / Confirm mapping
```

요구사항:

- 왼쪽 candidate queue는 카드형보다 빠르게 훑는 리스트형
- 유사도 순 정렬
- 가운데는 선택한 개념의 의미와 기존 연결 표시
- 오른쪽은 신규 개념 여러 개를 batch 처리
- 각 후보/step에 `Add to selected wiki`, `Merge into selected wiki`, `Create new`, `Edit`, `Reject + Retry`, `Confirm mapping` 액션
- 기존 wiki match 목록은 similarity 순으로 보여주고 `Use this wiki`/`Switch` 액션을 제공한다.
- 기존 wiki가 선택되지 않으면 Add/Merge CTA는 disabled 상태로 `select wiki` 안내를 표시한다.
- 모바일에서도 핵심 결정(`Reject + Retry`, `Confirm`)을 허용하되 단일 column stepper와 하단 sticky CTA로 실수 가능성을 낮춘다.
- Wiki compile preview는 필요할 때 펼치기

### 4. Graph Popup

- 선택 개념 중심 1-hop 관계
- `| 그래프 | wiki 내용 |` 구조
- graph node 클릭 시 wiki 내용 표시

### 5. Web Settings

- model 설정
- prompt 설정
- task별 prompt version 관리
- 변경점 logging
- prompt 변경 후 영향 안내

## 제외 기능

- 다중 사용자 권한
- 협업 승인 워크플로우
- 다중 사용자 메뉴/프로필 관리. Logout은 향후 사용자 메뉴 dropdown에 배치하며, 사용자 메뉴 구현 전에는 top-level nav에 표시하지 않는다.
- Web에서 Vault 무제한 직접 편집

## 성공 상태

- 대시보드에서 현재 처리 상태를 파악할 수 있다.
- Mapping 화면에서 신규 개념 여러 개를 batch 처리할 수 있다.
- 기존 wiki 유사도 목록과 선택 개념 내용을 비교해 병합/신규 결정을 할 수 있다.
- graph popup에서 1-hop 관계와 wiki 내용을 볼 수 있다.
- prompt 변경 이력이 남는다.

## 목업 검토 질문

1. 왼쪽 목록의 정보 밀도는 어느 정도가 적당한가?
2. 오른쪽 batch 카드에서 여러 항목을 동시에 병합/신규 처리하는 UX가 안전한가?
3. Settings의 prompt versioning은 Review 화면에서 바로 접근해야 하는가, 별도 Settings 화면이면 충분한가?


## Mockup approval reference

- Canonical HTML mockup: `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Legacy HTML mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`은 구현 기준이 아니다.
- PRV feedback: `.code-planner/02-planning/review/phase-3-prv-feedback.md`
- Approval status: approved

## 확정 보정

- Web Auth: `.env` 사용자 비밀번호 기반
- Prompt 변경: test version → test run → confirmed version
- Prompt log: 버전별 전체 저장 + change note

## UI 일치성 결정 — 2026-07-19

- Top nav 기준: `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings`.
- Logout 기준: top-level nav가 아니라 향후 사용자 메뉴 dropdown. 사용자 메뉴가 없으면 Settings > Auth의 임시 액션으로만 허용.
- PC submenu: Settings 같은 관리형 화면은 좌측 submenu 우선. Mapping은 상단 stepper + 좌측 candidate queue.
- Mobile menu: 상단 메뉴 나열 금지. compact header의 사이드 메뉴 버튼(☰)으로 drawer를 열고, drawer 안에서 top-level 메뉴와 Mapping/Settings 세부 메뉴에 진입.
- Mobile Mapping: 단일 column stepper + existing wiki 선택 영역 + 하단 sticky CTA.
- 버튼 token: primary/secondary/destructive/warn 4종, 최소 터치 영역 44px, mobile 주요 CTA는 하단 sticky.
- Breakpoint: desktop `>= 1024px`, tablet `768–1023px`, mobile `< 768px`.


## 확정 Web UI 기술스택

- Backend/API: FastAPI
- Server: uvicorn
- Template: Jinja2
- Forms: python-multipart
- Settings: PyYAML
- Env: python-dotenv
- Validation/schema: pydantic
- Frontend: server-rendered HTML + Vanilla JavaScript ES modules + plain CSS
- Graph popup: inline SVG + Vanilla JS
- Auth: `.env` 관리자 비밀번호 + stdlib hmac signed session cookie
- 제외: React/Vite/Next.js, Tailwind build pipeline, 외부 graph library 필수 의존, 다중 사용자 auth

Build agent는 위 dependency 추가를 승인된 것으로 본다. 이 목록 밖의 dependency가 필요하면 사용자 승인을 요청한다.
