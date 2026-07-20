# Phase 3 Page UX Spec — Mapping

## Review status

- Status: `drafted_review_pending`
- Source problem: 현재 구현된 Mapping 화면은 기존 wiki와 새로 생긴 개념/후보를 연결하는 목적이 명확하지 않다.
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- Mapping은 3단계 wizard로 구성한다.
- 단계: `1. Page 검증 → 2. Page Mapping → 3. Relationship 검증 → 4. 오류/에러`
- 각 단계에는 `Reject`, `Edit`, `Next`가 필요하다.
- 최종 `Confirm`은 3단계 Relationship 검증 이후에만 제공한다.
- `오류/에러` 탭은 같은 Mapping 페이지 안에서 문제 후보/실패 기록을 보고 `Retry with instruction`을 실행하는 진단/재시도 영역이다.
- 중간에 잘못된 부분은 사용자 수정 또는 `Reject + retry instruction`으로 처리한다.
- Mapping header에는 신규 처리 대상 수를 표시한다. 예: `Mapping [new: 3건]`
- Step 2 Page Mapping 결정은 radio로 고정한다: `Merge into existing` / `Keep as new page` / `Unsure, defer`.
- Step 3 Relationship 검증은 PC에서 graph + list, 모바일에서 list 우선으로 표시한다.
- Page name: `Mapping`.

## 1. 페이지 목적

Mapping 페이지는 자동 처리 이후 생성된 신규 wiki/page 후보를 사람이 3단계로 검토하여 최종 반영 여부를 결정하는 화면이다.

1. Page 검증: LLM이 제시한 wiki page 자체가 타당한지 확인
2. Page Mapping: 기존 wiki와 겹치거나 매핑될 대상이 있는지 확인
3. Relationship 검증: 최종 wiki 관계 구조가 맞는지 확인
4. Confirm: 3단계가 모두 통과한 뒤 반영

이 페이지는 내부 `map` 작업을 실행하는 화면이 아니다. 내부 `map`은 후보를 만드는 자동 처리 단계이고, Mapping 페이지는 생성된 후보를 사람이 결정하는 단계다.

```text
Inbox 처리 완료 → 후보 생성 → Page 검증 → Page Mapping → Relationship 검증 → Confirm 반영
```

## 1-0. 3단계 Mapping wizard 개요

```text
Mapping [new: 3건]

1. Page 검증
   LLM이 만든 wiki name / 사유 / 본문 / relationship 초안을 검토
   [Reject] [Edit] [Next]

2. Page Mapping
   후보 page와 기존 wiki 유사 항목을 비교
   [Reject] [Edit] [Next]

3. Relationship 검증
   매핑 완료 기준으로 기존 wiki와 연결된 구조를 확인
   [Reject] [Edit] [Confirm]
```

진행 원칙:

- `Next`는 해당 단계 검토가 끝났다는 의미다.
- `Confirm`은 최종 반영이다.
- 1~2단계에서는 confirm을 제공하지 않는다.
- 사용자가 수정하면 수정된 값으로 다음 단계에 전달한다.
- Reject는 항상 retry instruction 입력을 요구한다.

## 1-0-1. 단계별 목적

| Step | 목적 | 사용자가 보는 것 | 주요 결정 |
|---|---|---|---|
| 1. Page 검증 | LLM이 만든 page 후보 자체가 맞는지 확인 | wiki name, 생성 사유, 본문, relationship 초안 | 이 후보를 계속 검토할지 / 수정할지 / reject할지 |
| 2. Page Mapping | 기존 wiki와 같은지, 합칠지, 새로 만들지 판단 | 후보 wiki name/본문 + 기존 유사 wiki list 비교 | 기존 wiki에 merge/map할지, 신규 page로 둘지 |
| 3. Relationship 검증 | 최종 연결 구조가 맞는지 확인 | 현재 후보가 기존 wiki들과 연결된 graph/list | relation이 맞는지, 방향/라벨을 수정할지, 최종 confirm할지 |

## 1-0-2. 단계별 공통 액션

### Reject

- 현재 후보를 그대로 반영하지 않는다.
- retry instruction 입력 필수.
- 예:

```text
이 후보는 RAG와 Agentic RAG를 구분하지 못했습니다.
Agentic RAG를 별도 개념으로 다시 평가해주세요.
```

### Edit

- 현재 단계에서 사용자가 값을 수정한다.
- 수정 가능한 항목은 단계별로 다르다.
- 수정 후 `Next` 가능.

### Next

- 현재 단계 검토 완료.
- 다음 단계로 이동.
- DB에는 최종 반영하지 않고 draft decision으로 저장한다.

### Confirm

- 3단계 Relationship 검증 이후에만 가능.
- 확정 반영.
- Inbox completed result record와 연결.

## 1-1. Mapping의 평가 단위

Mapping은 “후보 하나 ↔ 기존 wiki 하나”만 보는 화면이 아니다. 실제 사용에서는 **wiki 한 개를 열고 그 wiki와 관련된 여러 후보를 평가**하는 구조가 필요하다.

예:

```text
현재 wiki: RAG

평가 후보:
- alias 후보: Retrieval Augmented Generation
- claim 후보: RAG는 검색 결과를 LLM 생성에 결합한다
- relation 후보: RAG -> Vector Search
- relation 후보: RAG -> Agentic RAG
- 신규 개념 후보: Agentic RAG
```

결정 단위:

- 후보별 개별 승인/거절
- 여러 후보 batch 승인
- relation 후보는 source/target/direction/label 확인 후 승인
- 신규 개념 후보는 현재 wiki와 relation으로 연결하거나 별도 생성

## 1-2. 사람이 평가하는 3단계

Mapping에서 사용자가 판단해야 하는 핵심은 아래 3가지다.

```text
1. 설명과 wiki 제목이 맞는가?
2. 기존에 있던 단어/개념과 겹치는가?
3. 다른 관계와 연결할 때 유사한 단어/개념이 이미 있는가?
```

### 1단계 — 설명과 wiki 제목이 맞는가?

질문:

- LLM이 제안한 제목/개념이 이 설명과 같은 의미인가?
- 이 후보가 현재 열려 있는 wiki 페이지에 붙을 내용인가?
- 아니면 별도 개념인가?

사용자 결정:

- 현재 wiki에 추가
- 새 wiki로 분리
- 틀렸으면 reject/retry

### 2단계 — 기존에 있던 단어와 겹치는가?

질문:

- 후보 이름이 기존 alias/title과 같은 의미인가?
- 철자만 다른가?
- 약어/풀네임 관계인가?

사용자 결정:

- alias로 추가
- 기존 wiki에 merge
- 새 개념으로 생성

### 3단계 — 관계 연결 시 유사한 단어가 이미 있는가?

질문:

- relation target/source가 이미 존재하는 wiki인가?
- 비슷한 이름의 wiki가 이미 있는가?
- 새 relation을 만들지, 기존 relation을 강화/확인할지?

사용자 결정:

- existing wiki와 relation 추가
- 기존 relation confirm/keep
- 신규 target concept 생성 후 relation 추가
- defer

## 1-3. LLM JSON이 만들어와야 할 것과 사용자가 결정할 것

### LLM이 JSON으로 만들어와야 할 것

LLM은 최종 결정을 하지 않고, 사람이 판단할 수 있는 후보와 근거를 만든다.

```text
- 후보 제목/title
- 후보 설명/summary
- 후보 타입: alias / claim / relation / concept
- evidence quote + locator
- 기존 wiki와의 유사 후보 목록
- 겹칠 수 있는 기존 단어/alias/title
- relation 후보의 source / target / label / direction
- LLM 추천 action
- confidence
- reason
```

### 사용자가 연결하는 것

사용자는 LLM 추천을 보고 아래 중 하나를 결정한다.

```text
- 현재 wiki에 alias 추가
- 현재 wiki에 claim 추가
- 현재 wiki와 기존 wiki 사이 relation 추가
- 기존 wiki에 merge
- 새 wiki 생성
- 새 wiki 생성 후 relation 추가
- defer
- reject + retry
```

### UI에 보이는 평가 순서

Mapping 후보 detail은 이 순서로 보여준다.

```text
① 제목/설명 확인
② 기존 단어/개념 중복 확인
③ 관계 대상 중복/유사 확인
④ 결정 버튼
```

## 2. 핵심 UX 문제와 해결 방향

### 문제

- 새 후보와 현재 wiki의 관계가 명확하지 않음.
- 어떤 relation/claim/alias가 현재 wiki에 추가되는지 불분명함.
- `merge`, `new` 버튼이 어떤 대상에 적용되는지 모호함.
- 후보 목록이 카드형으로 커서 많이 훑기 어렵고, 핵심 정보가 묻힘.
- LLM이 왜 이 후보를 만들었는지, 어떤 신규 값인지 한눈에 보이지 않음.

### 해결 방향

- 먼저 기존 wiki를 선택하고 본문을 읽는다.
- 우상단 후보 list에는 현재 wiki와 관련된 여러 후보를 type별로 보여준다.
- 후보를 열면 해당 후보가 현재 wiki에 어떤 변경을 제안하는지 보여준다.
- relation 후보는 source → target 방향과 relation label을 명확히 보여준다.
- add/merge 버튼에는 현재 wiki와 변경 대상을 포함한다.
- create new 버튼에는 생성될 신규 개념 이름과 현재 wiki와의 relation 여부를 포함한다.
- 후보 목록은 compact floating/list 형태로 작게 유지한다.

## 3. PC 기본 화면 구조

PC 기본 구조는 3단계 wizard를 기준으로 한다. 상단에는 신규 후보 수와 step progress가 보이고, 본문은 현재 step의 검토 대상에 맞춰 바뀐다.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Mapping [new: 3건]                                                   │
│ ① Page 검증  →  ② Page Mapping  →  ③ Relationship 검증  →  ④ 오류/에러 │
├─────────────────────────────────────────────────────────────────────┤
│ Left: New candidate queue      │ Center: Step workspace                │
│ - 후보 1                       │ - step별 검토 화면                    │
│ - 후보 2                       │ - 비교/본문/relationship view         │
│ - 후보 3                       │                                       │
├─────────────────────────────────────────────────────────────────────┤
│ Sticky action bar: Reject · Edit · Next / Confirm                     │
└─────────────────────────────────────────────────────────────────────┘
```

### PC interaction model

1. 왼쪽 신규 후보 queue에서 처리할 후보를 선택한다.
2. Step 1 Page 검증에서 LLM이 만든 wiki name/사유/본문/relationship 초안을 확인한다.
3. 문제가 있으면 Edit 또는 Reject, 괜찮으면 Next.
4. Step 2 Page Mapping에서 기존 유사 wiki와 나란히 비교한다.
5. 기존과 같으면 merge/map, 다르면 신규 page로 유지하도록 선택하고 Next.
6. Step 3 Relationship 검증에서 최종 연결 구조를 확인한다.
7. 관계 방향/라벨/대상이 맞으면 Confirm으로 반영한다.
8. 오류가 있거나 재시도가 필요하면 ④ 오류/에러 탭에서 retry instruction을 작성한다.

## 4. Tablet/Mobile 구조

Tablet:

- 기존 wiki list + 본문을 기본으로 둔다.
- 신규 후보는 floating button/drawer로 연다.
- 후보 선택 후 split 또는 drawer에서 비교한다.

Mobile:

```text
Candidate queue
→ ① Page 검증
→ ② Page Mapping
→ ③ Relationship 검증
→ ④ 오류/에러
→ Confirm
```

Sticky CTA는 항상 현재 선택 상태를 반영한다.

모바일 핵심 원칙:

- 신규 후보와 기존 개념을 동시에 넓게 보여주기 어렵기 때문에 “전환하며 비교”하는 흐름을 사용한다.
- 상단에는 현재 비교 상태를 짧게 표시한다.

```text
Candidate: Agentic RAG
Step: 2 / 3 Page Mapping
```

## 4-1. Step 1 — Page 검증

목적: LLM이 제시한 wiki page 후보 자체가 맞는지 확인한다.

보여줄 정보:

- LLM 제안 wiki name
- 생성 사유
- LLM이 만든 본문 preview
- LLM이 예상한 relationship 초안
- source/evidence
- model/prompt/schema summary

화면 예:

```text
① Page 검증

Wiki name
Agentic RAG

LLM reason
RAG와 관련되지만 agent decision loop가 있어 별도 개념으로 보입니다.

Draft body
Agentic RAG is ...

Proposed relationships
Agentic RAG --specializes--> RAG
Agentic RAG --uses--> Tool Use

[Reject] [Edit] [Next]
```

Edit 가능 항목:

- wiki name
- summary/body
- relationship 초안 삭제/수정

Next 조건:

- wiki name이 비어 있지 않음
- 본문 또는 요약이 있음

## 4-2. Step 2 — Page Mapping

목적: 후보 page가 기존 wiki와 같은지, 합칠지, 신규로 둘지 판단한다.

보여줄 정보:

- 후보 wiki name
- 후보 본문 preview
- 기존 wiki 유사도 높은 항목 list
- 선택한 기존 wiki 본문 preview
- 중복 alias/title 표시
- LLM 추천: merge / create new / uncertain

PC 화면:

```text
② Page Mapping

Left: Candidate page          Right: Similar existing wiki
Agentic RAG                   RAG 0.72
본문 preview                  LLM Agent 0.68
                              Agent Pattern 0.61

Selected existing wiki preview
RAG 본문...

Decision draft
( ) Merge into RAG
(•) Keep as new page
( ) Unsure, defer

[Reject] [Edit] [Next]
```

Edit 가능 항목:

- merge target 변경
- 신규 page로 유지
- wiki name 수정
- body 수정

Next 조건:

- `Merge into existing` / `Keep as new page` / `Unsure, defer` 중 하나가 선택됨
- `Merge into existing` 선택 시 merge target이 선택됨

## 4-3. Step 3 — Relationship 검증

목적: page mapping 결정 이후, 최종 wiki 연결 구조가 맞는지 검증한다.

보여줄 정보:

- 최종 page 또는 merge target
- 연결될 기존 wiki 목록
- relation label
- direction
- evidence
- PC: mini graph + relation list
- Mobile: relation list 우선, graph는 접힘/secondary
- 클릭 시 연결 대상 wiki preview

화면 예:

```text
③ Relationship 검증

Agentic RAG --specializes--> RAG
Agentic RAG --uses--> Tool Use

Click relation to preview target wiki.

[Reject] [Edit] [Confirm]
```

Edit 가능 항목:

- relation 삭제
- relation label 수정
- direction 변경
- target wiki 변경
- relation defer 처리

Confirm 조건:

- 모든 required relationship이 승인/삭제/defer 중 하나로 결정됨
- page mapping 결정이 완료됨

Confirm 결과:

- wiki 반영 또는 반영 계획 저장
- Mapping candidate 상태 업데이트
- Inbox completed record에 model/result/artifact와 연결

## 4-4. Step 4 — 오류/에러

목적: 같은 Mapping 페이지 안에서 후보/단계별 오류를 확인하고 `Retry with instruction`을 실행한다.

이 탭은 최종 confirm 단계가 아니다. 오류 진단과 재시도 요청을 위한 탭이다.

보여줄 정보:

- 오류가 발생한 후보
- 오류가 발생한 단계
  - Page 검증
  - Page Mapping
  - Relationship 검증
- error summary
- failed model run summary
- schema validation error, if any
- related source/evidence
- retry history
- technical details 접힘

화면 예:

```text
④ 오류/에러

Candidate: Agentic RAG
Failed step: Page Mapping
Reason: 기존 RAG와 신규 Agentic RAG를 구분하지 못함

Retry instruction
[ Agentic RAG는 RAG와 별도 개념으로 보고, RAG와 specializes 관계로 연결해줘. ]

[Retry with instruction] [Mark as rejected] [Back to Step 2]
```

액션:

- `Retry with instruction`
- `Mark as rejected`
- `Back to failed step`
- `View technical details`

Retry instruction 정책:

- 필수 입력
- 재시도 대상 후보/단계와 연결 저장
- 재시도 후 후보가 새로 생성되면 Mapping queue에 새 revision으로 표시
- 이전 실패 기록은 completed/error record에 남김

오류 tab 진입 방식:

- step 내 오류 banner에서 `Open 오류/에러`
- 왼쪽 candidate queue의 warning chip 클릭
- Dashboard Issues에서 Mapping 오류 클릭

## 5. 왼쪽 — Existing wiki list

목적: 기존 wiki 개념을 빠르게 선택한다.

표시:

- wiki title
- file path 또는 folder hint
- similarity badge, 후보가 선택된 경우
- aliases/relations count
- updated time, optional

형태:

```text
RAG                         0.91
10_Wiki/concepts/rag.md

Retrieval Augmented Gen.     0.78
10_Wiki/concepts/retrieval-augmented-generation.md
```

검색/필터:

- title search
- alias search
- high similarity only
- recently updated

## 6. 중앙 — Existing wiki document

목적: 기존 개념의 본문을 읽고, 현재 후보와 연결해도 되는지 판단한다.

표시:

- rendered Markdown body
- file path at top
- frontmatter는 본문 상단에 직접 노출하지 않음
- aliases/claims/relations 요약
- 1-hop relation mini preview 또는 Wiki 페이지로 이동
- raw markdown은 details로 숨김

## 7. 우상단 floating — Candidate stack

목적: 현재 wiki와 관련된 여러 후보를 빠르게 훑고 평가한다.

표시:

- candidate title
- type icon/chip
  - concept
  - claim
  - relation
  - mapping
- source title
- confidence/similarity chip
- status
  - pending
  - selected
  - decided
  - retry_requested

접힌 형태:

```text
┌────────────────────┐
│ 🧩 Candidates 8     │
│ claims 2 · rel 4    │
└────────────────────┘
```

확장 형태:

```text
Claims
  ▣ RAG combines retrieval with generation · 0.88

Relations
  🔗 RAG → Vector Search · uses · 0.91
  🔗 RAG → Agentic RAG · related_to · 0.76

New concepts
  🧩 Agentic RAG · 0.82
```

후보 row는 작게 유지하고 type별로 group한다. 클릭 시 floating panel 안에서 detail이 확장된다. 중앙 본문은 기존 wiki 문서를 유지한다.

필터:

- All
- Concepts
- Claims
- Relations
- High similarity
- Retry needed

## 8. Floating 확장 — Candidate detail

목적: “새로 생긴 값이 무엇인지”와 “LLM이 왜 그렇게 판단했는지”를 보여준다.

표시:

### Proposed value

- candidate title/name
- candidate type
- proposed aliases
- proposed summary
- proposed claims/relations

Relation 후보일 때 추가 표시:

- source concept
- target concept
- direction
- relation label
- confidence
- relation이 현재 wiki에 추가되는 방향인지, 현재 wiki에서 다른 wiki로 나가는 방향인지

예:

```text
Relation candidate
RAG --uses--> Vector Search
현재 wiki “RAG”에 outgoing relation으로 추가됩니다.
```

### LLM evaluation

- LLM 판단 요약
- confidence
- mapping suggestion
  - likely existing
  - likely new
  - uncertain
- reason

### Evidence

- source file/title
- quote/snippet
- locator/page/chunk
- raw source link

### Technical details

기본 숨김:

- candidate JSON
- raw LLM response
- schema validation result
- model/prompt info는 요약만 보이고 details에서 전체 표시

## 9. Existing wiki match hint

목적: 선택한 신규 후보 기준으로 기존 wiki 목록/현재 문서가 적절한지 힌트를 준다.

표시:

- current wiki similarity
- other similarity-ranked wiki concepts as suggestions
- exact/alias match badge
- relation proximity badge
- “switch to this wiki” action

형태:

```text
Existing wiki matches

◎ RAG                         0.91 exact alias
  /10_Wiki/concepts/rag.md

○ Retrieval Augmented Gen.     0.78 related
  /10_Wiki/concepts/retrieval-augmented-generation.md
```

현재 열린 existing wiki가 없으면 merge CTA는 disabled.

## 8. Decision action bar

목적: 어떤 후보를 어디에 반영하는지 버튼에서 명확히 보여준다.

상태별 버튼:

### current wiki와 candidate가 선택됨

```text
[Add to “RAG”] [Merge into “RAG”] [Create new “Agentic RAG”] [Edit] [Reject + Retry]
```

후보 type별 primary action:

| Candidate type | Primary action |
|---|---|
| alias | `Add alias to “RAG”` |
| claim | `Add claim to “RAG”` |
| relation | `Add relation RAG → Target` |
| concept | `Create new “Candidate”` 또는 `Merge into “RAG”` |
| mapping | `Confirm mapping` |

### current wiki 미선택

```text
[Merge disabled: select wiki] [Create new “Agentic RAG”] [Edit] [Reject + Retry]
```

### action confirmation

Relation/claim 추가 클릭 시 확인:

```text
현재 wiki “RAG”에 relation을 추가합니다.
RAG --uses--> Vector Search
Evidence: paper-rag.md #chunk-3
[Confirm add] [Cancel]
```

Merge 클릭 시 확인:

```text
“Agentic RAG” 후보를 기존 wiki “RAG”에 병합합니다.
추가될 값: aliases 1, claims 2, relations 1
[Confirm merge] [Cancel]
```

Create new 클릭 시 확인:

```text
신규 wiki 개념 “Agentic RAG”를 생성합니다.
생성 위치: 10_Wiki/concepts/agentic-rag.md
[Create concept] [Cancel]
```

Reject + Retry:

- reject reason 필수
- retry instruction 필수

## 9. Mapping 결과 상태

결정 후 후보 상태:

- merged
- created
- added_claim
- added_relation
- added_alias
- edited
- retry_requested
- rejected

Inbox completed record에는 이 결정 결과가 연결되어야 한다.

## 10. Empty/Error 상태

Mapping 오류는 현재 후보의 현재 step에서 감지하고, ④ 오류/에러 탭에서 retry/reject를 처리한다.

권장 위치:

- 왼쪽 candidate queue: 문제 후보 row에 warning/failed chip
- Step 1 Page 검증: page 후보 JSON/schema/title/body 오류
- Step 2 Page Mapping: 유사 wiki load 실패, merge target 불명확
- Step 3 Relationship 검증: relation direction/label/target 오류
- Step 4 오류/에러: retry with instruction, rejected, technical details
- 하단 action bar: decision 저장 실패

오류별 CTA:

| 오류 | CTA |
|---|---|
| 후보 내용 오류 | `Edit` / `Reject + retry instruction` |
| 유사 wiki 검색 실패 | `Retry search` |
| merge target 불명확 | `Select target` / `Edit` |
| relation 방향 오류 | `Edit relation` |
| confirm 저장 실패 | `Retry save` / `View technical details` |
| LLM 재평가 필요 | `Retry with instruction` |

### No candidates

```text
검토할 후보가 없습니다.
[Open Inbox] [Scan folder]
```

### No wiki matches

```text
유사한 기존 wiki가 없습니다.
[Create new “candidate”]를 권장합니다.
```

### Candidate load failed

```text
후보 정보를 불러오지 못했습니다.
[Retry] [View log]
```

### Decision failed

```text
결정 저장에 실패했습니다.
[Retry] [View technical details]
```

## 11. 필요한 API 초안

```text
GET  /api/mapping/candidates
GET  /api/mapping/candidates/{candidate_id}
GET  /api/mapping/wiki-matches?candidate_id=...
GET  /api/mapping/wiki/{concept_id}
POST /api/mapping/decide
POST /api/mapping/candidates/{candidate_id}/edit
```

Decision payload 예:

```json
{
  "candidate_id": "cand_123",
  "action": "merge",
  "target_concept_id": "concept_rag",
  "reason": "same concept",
  "selected_additions": {
    "aliases": ["Agentic RAG"],
    "claims": ["..."],
    "relations": ["..."]
  }
}
```

## 12. 승인 기준

- 사용자가 Mapping이 3단계 검증 과정임을 즉시 이해한다.
- `Mapping [new: N건]`으로 처리 대상 수가 보인다.
- Step 1 Page 검증에서 LLM wiki name/사유/본문/relationship 초안이 보기 쉽게 보인다.
- Step 2 Page Mapping에서 후보 page와 기존 유사 wiki를 나란히 비교할 수 있다.
- Step 3 Relationship 검증에서 최종 연결 구조를 graph/list로 보고 클릭해 대상 wiki를 확인할 수 있다.
- 각 단계에 `Reject`, `Edit`, `Next`가 있다.
- `Confirm`은 3단계에서만 보인다.
- raw JSON/LLM response는 기본 숨김이다.
- 결정 후 Inbox completed record와 연결된다.

## 13. 확인 필요

- 현재 없음. Mapping UX는 임시 확정 상태로 다음 페이지 검토로 넘어갈 수 있다.
