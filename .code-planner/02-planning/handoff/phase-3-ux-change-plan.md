# Phase 3 UX Change Plan — Mobile Side Menu + Mapping Actions

## 목적

이 문서는 전체 Phase 3 계획서가 아니라, 현재 승인 후보 목업을 기준으로 Build 단계에 지시할 **UX 변경 건**만 정의한다.

## 기준 목업

- HTML mockup: `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Review note: `.code-planner/02-planning/review/phase-3-ui-consistency-review.md`
- Latest PRV review: `http://100.66.135.34:36303/session/20260719T125745Z-43932b`

## 변경 범위

### 포함

1. Mobile navigation UX 변경
2. Mapping 화면의 existing wiki match/매핑 액션 복원 및 명확화
3. PC/Mobile 버튼 위치와 CTA 노출 기준 정리

### 제외

- 전체 Phase 3 재설계
- 데이터 schema 변경
- LLM candidate 생성 로직 변경
- 신규 사용자/프로필 메뉴 구현
- 다중 사용자 권한

---

# 1. Mobile navigation 변경

## 현재 문제

- 모바일에서 상단 메뉴를 나열하면 화면 폭이 부족하고 세부 메뉴 진입이 불명확하다.
- Mapping step, Settings section 같은 2차 메뉴가 어디에 위치해야 하는지 모호했다.

## 변경 지시

Mobile `<768px`에서는 상단 메뉴 항목을 나열하지 않는다.

```text
상단 header:
[☰] LLM Wiki Local
```

`☰` 버튼을 누르면 좌측 side drawer가 열린다.

Drawer 안에는 다음 항목을 둔다.

```text
Main
- Onboarding
- Dashboard
- Inbox
- Mapping
  - ① Page 검증
  - ② Page Mapping
  - ③ Relationship 검증
  - ④ 오류/에러
- Vault
- Wiki
- Settings
  - LLM
  - Prompt
  - Vault
  - Auth / Logout
```

## 수용 기준

- [ ] 모바일 상단에 전체 메뉴가 가로 나열되지 않는다.
- [ ] `☰` 버튼이 44px 이상 터치 영역을 가진다.
- [ ] drawer에서 top-level 메뉴와 Mapping/Settings 세부 메뉴에 접근 가능하다.
- [ ] drawer 항목은 현재 위치(active)를 표시한다.
- [ ] 사용자 메뉴가 없으므로 Logout은 top nav에 두지 않고 `Settings > Auth` 임시 액션으로만 둔다.

---

# 2. Mapping existing wiki action 변경

## 현재 문제

- 재작성된 목업에서 기존 wiki와 매핑할 버튼 액션이 보이지 않았다.
- 기존 요청의 핵심인 “기존 wiki 선택 후 Add/Merge/Create/Confirm” 흐름이 누락되었다.

## 변경 지시

Mapping 화면에는 반드시 `Existing wiki matches` 영역이 있어야 한다.

예시:

```text
Existing wiki matches

◎ RAG                         0.91 exact alias
  /10_Wiki/concepts/rag.md     [Use this wiki]

○ Retrieval Augmented Gen.     0.78 related
  /10_Wiki/concepts/...        [Switch]
```

기존 wiki가 선택된 경우 action bar는 다음 액션을 명확히 보여준다.

```text
[Add to “RAG”]
[Merge into “RAG”]
[Create new “Agentic RAG”]
[Edit]
[Reject + Retry]
[Confirm mapping]
```

기존 wiki가 선택되지 않은 경우:

```text
[Add disabled: select wiki]
[Merge disabled: select wiki]
[Create new “Agentic RAG”]
[Edit]
[Reject + Retry]
```

## 수용 기준

- [ ] 기존 wiki 후보 목록이 similarity 순으로 보인다.
- [ ] 각 후보에 `Use this wiki` 또는 `Switch` 액션이 있다.
- [ ] 선택된 wiki 이름이 action button label에 포함된다. 예: `Merge into “RAG”`
- [ ] Add/Merge/Create의 의미가 버튼 label만 보고 구분된다.
- [ ] `Confirm mapping`은 최종 확정 액션으로 별도 표시된다.
- [ ] 기존 wiki 미선택 상태에서는 Add/Merge가 disabled이고 이유가 보인다.

---

# 3. PC layout 지시

PC `>=1024px`에서는 다음 구조를 따른다.

```text
Top nav:
Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings

Mapping:
상단: Page 검증 → Page Mapping → Relationship 검증 → 오류/에러
좌측: Candidate queue + Existing wiki matches
우측: 현재 step workspace + Mapping preview + Action bar
```

## 수용 기준

- [ ] PC에서는 top nav를 유지한다.
- [ ] Mapping 좌측에는 candidate queue와 existing wiki matches가 함께 보인다.
- [ ] Mapping 우측에는 selected wiki, preview, action bar가 보인다.
- [ ] action bar는 화면 하단에 숨어 있지 않고 즉시 발견 가능하다.

---

# 4. Mobile Mapping layout 지시

Mobile `<768px`에서는 다음 구조를 따른다.

```text
[☰] LLM Wiki Local
Mapping

Candidate: Agentic RAG
Existing wiki: RAG [Switch]
Current step card
Preview/details

Sticky CTA:
[Merge into RAG] [Create new]
[Reject + Retry] [Confirm]
```

## 수용 기준

- [ ] Mapping step 전환은 side drawer nested menu에서 가능하다.
- [ ] 본문은 단일 column이다.
- [ ] 기존 wiki 선택/전환이 모바일에서도 가능하다.
- [ ] 주요 mapping 액션이 하단 sticky CTA 또는 동등하게 항상 발견 가능한 위치에 있다.
- [ ] `Reject + Retry`와 `Confirm`은 모바일에서도 제거하지 않는다.

---

# 5. 버튼/크기 지시

## 버튼 variant

- Primary: 주요 진행/선택 액션
- Secondary: 보조 액션
- Warn: 신규 생성처럼 되돌리기 전 확인이 필요한 액션
- Destructive: Reject/Retry/Logout 등 위험 액션

## 크기

- Desktop button height: 36–40px
- Mobile touch target: 44px 이상

## 수용 기준

- [ ] 모바일 CTA는 44px 이상이다.
- [ ] 위험 액션은 primary와 시각적으로 구분된다.
- [ ] 같은 의미의 버튼 label이 PC/Mobile에서 다르게 축약되어 혼동되지 않는다.

---

# 6. Build 작업 순서 제안

1. 기존 Phase 3 UI에서 mobile top menu 가로 나열 제거
2. mobile header에 `☰` 버튼 추가
3. side drawer 컴포넌트/템플릿 추가
4. drawer에 top-level + nested menu 구성
5. Mapping 화면에 `Existing wiki matches` 영역 추가
6. selected wiki 상태와 action label 연결
7. Add/Merge disabled 상태 처리
8. Mobile sticky CTA에 mapping action 반영
9. PC/Mobile viewport 수동 검증

---

# 7. 검증 체크리스트

## Desktop

- [ ] 1440px에서 top nav가 정상 표시된다.
- [ ] Mapping에서 기존 wiki 후보와 매핑 버튼이 동시에 보인다.
- [ ] `Merge into “RAG”`, `Add to “RAG”`, `Create new “Agentic RAG”`가 구분된다.

## Mobile

- [ ] 390px 폭에서 상단 메뉴가 나열되지 않는다.
- [ ] `☰`로 drawer를 열 수 있다.
- [ ] drawer에서 Mapping step에 진입할 수 있다.
- [ ] Mapping에서 기존 wiki 선택/전환이 가능하다.
- [ ] 하단 CTA에 기존 wiki 매핑 액션이 보인다.

## Regression fail 조건

- mobile에서 상단 메뉴를 다시 가로 나열하면 fail.
- Mapping에서 existing wiki match 영역이 사라지면 fail.
- Add/Merge/Create/Confirm mapping 액션 중 하나라도 사라지면 fail.
- mobile에서 `Reject + Retry` 또는 `Confirm`을 제거하면 fail.
- Logout을 top-level nav에 다시 추가하면 fail.
