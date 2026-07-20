# Markdown Mockup — Phase 3 Web Review UI

> 주의: 이 문서는 Ideation/Planning용 텍스트 목업이다. 최종 승인 전에는 HTML 목업과 시각 검토가 필요하다.

## 2026-07-19 UI 일치성 보정

- 구현 기준 HTML은 `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`이다.
- `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`은 legacy 참고용이며, 통합 mockup과 충돌하면 통합 mockup을 우선한다.
- 기본 지원 범위는 PC + Mobile이다.
- Top nav: `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings`.
- Logout: top-level nav에 두지 않고 향후 사용자 메뉴 dropdown에 배치한다. 사용자 메뉴가 아직 없으면 Settings > Auth에 임시 배치한다.
- Mobile navigation: 상단 메뉴 나열이 아니라 사이드 메뉴 버튼(☰)으로 drawer를 열고 세부 메뉴에 진입한다.
- Mobile Mapping: `Reject + Retry`, `Confirm` 핵심 결정을 허용한다. 단일 column stepper + 하단 sticky CTA를 사용한다.
- Breakpoint: desktop `>= 1024px`, tablet `768–1023px`, mobile `< 768px`.

## 화면 1. Login

```text
┌──────────────────────────────────────────────┐
│ LLM Wiki Local                               │
│                                              │
│ Password / Token                             │
│ [________________________________________]   │
│                                              │
│ [로그인]                                     │
│                                              │
│ local admin only                             │
└──────────────────────────────────────────────┘
```

검토 질문:

- 로컬 전용이면 token/password 중 무엇이 충분한가?

## 화면 2. Dashboard

```text
┌────────────────────────────────────────────────────────────────────┐
│ LLM Wiki Local  [Onboarding] [Dashboard] [Inbox] [Mapping] [Vault] [Wiki] [Settings] │
├────────────────────────────────────────────────────────────────────┤
│ 자료 처리 현황                                                     │
│  - 승인 필요: 12                                                   │
│  - pending: 8                                                      │
│  - 오류: 2                                                        │
│  - wiki 개수: 143                                                  │
│  - 시스템 상태: DB OK / LLM OK / Embedding OK / Sync Warning       │
├────────────────────────────────────────────────────────────────────┤
│ 빠른 액션                                                         │
│ [Inbox Scan] [Failed Jobs] [Review Queue] [Model Test] [Sync]      │
├────────────────────────────────────────────────────────────────────┤
│ 최근 작업                                                         │
│ source.md   chunked → embedded → needs_review                     │
│ paper.md    extract failed → retry_needed                         │
└────────────────────────────────────────────────────────────────────┘
```

상태:

- empty: 처리할 자료 없음
- success: 전체 시스템 OK
- failure: DB/LLM/Embedding/Sync 오류 강조

## 화면 3. Mapping Main

통합 구조:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Mapping  [① Page 검증] [② Page Mapping] [③ Relationship 검증] [오류/에러] │
├────────────────────────┬─────────────────────────────────────────────┤
│ Candidate queue        │ 현재 step workspace                         │
│ - Agentic RAG  1/3     │ # Agentic RAG                               │
│ - Tool-use RAG new     │ LLM reason / evidence / wiki preview        │
│ - RAG Agent error      │ 관계 후보와 compile preview                 │
│ Existing wiki matches  │ [Add to “RAG”] [Merge into “RAG”]            │
│ ◎ RAG 0.91 [Use this]  │ [Create new “Agentic RAG”] [Edit]           │
│ ○ Retrieval [Switch]   │ [Reject + Retry] [Confirm mapping]          │
└────────────────────────┴─────────────────────────────────────────────┘
```

Mobile:

```text
┌──────────────────────────────┐
│ [☰] LLM Wiki Local          │
│ Mapping                      │
│ 사이드 메뉴에서 ①/②/③/오류 step 선택 │
├──────────────────────────────┤
│ Candidate: Agentic RAG 1/3   │
│ Existing wiki: RAG [Switch]  │
│ 현재 step card               │
│ Wiki preview / details       │
├──────────────────────────────┤
│ sticky CTA: [Merge into RAG] [Create new] │
│             [Reject+Retry] [Confirm]      │
└──────────────────────────────┘

사이드 메뉴 drawer:

```text
┌──────────────────────────────┐
│ LLM Wiki Local        [닫기] │
├──────────────────────────────┤
│ Onboarding                   │
│ Dashboard                    │
│ Inbox                        │
│ Mapping                      │
│   ① Page 검증                │
│   ② Page Mapping             │
│   ③ Relationship 검증        │
│   ④ 오류/에러                │
│ Vault                        │
│ Wiki                         │
│ Settings                     │
│   LLM / Prompt / Vault / Auth│
└──────────────────────────────┘
```
```

주요 상호작용:

1. candidate queue에서 신규 후보를 선택한다.
2. `Page 검증 → Page Mapping → Relationship 검증` 순서로 검토한다.
3. Existing wiki matches에서 기존 wiki를 선택하거나 전환한다.
4. 같은 개념이면 `Merge into “RAG”`, 기존 문서에 값만 추가하면 `Add to “RAG”`, 다른 개념이면 `Create new “Agentic RAG”`로 확정한다.
5. 기존 wiki가 선택되지 않으면 merge/add 버튼은 disabled 상태로 `select wiki` 안내를 보여준다.
6. 틀리면 오류/에러 tab에서 `reject + retry instruction`을 입력한다.
7. 모바일에서도 `Merge/Add/Create`, `Reject + Retry`, `Confirm` 가능하되 하단 sticky CTA로 노출한다.
8. 필요하면 `Wiki Compile Preview`를 펼친다.

상태:

- empty: 신규 후보 없음
- success: 병합/신규 처리 완료
- failure: retry instruction 필요, LLM/DB 오류

## 화면 4. Graph Popup

```text
┌──────────────────────────────────────────────────────────┐
│ Graph: RAG 중심 1-hop                         [닫기]      │
├──────────────────────────────┬───────────────────────────┤
│ 그래프                       │ wiki 내용                 │
│                              │                           │
│        Agentic RAG           │ # Vector Search           │
│             │                │ summary: ...              │
│ RAG ─── uses ─── Vector      │ aliases: ...              │
│             │                │ related claims...         │
│        LLM Agent             │                           │
│                              │                           │
│ * 노드 클릭 시 오른쪽 갱신   │                           │
└──────────────────────────────┴───────────────────────────┘
```

검토 질문:

- 1-hop만으로 충분한가?
- graph node 클릭 시 표시할 wiki 내용 범위는 summary/claims/relations 중 어디까지인가?

## 화면 5. Settings — Prompt Versioning

```text
┌──────────────────────────────────────────────────────────┐
│ Settings > Prompts                                      │
├──────────────────────────────────────────────────────────┤
│ Task Type        Current Version       Actions           │
│ extract_claims   v3                    [Edit] [History]  │
│ map_candidates   v2                    [Edit] [History]  │
│ compile_wiki     v1                    [Edit] [History]  │
├──────────────────────────────────────────────────────────┤
│ Prompt Editor                                            │
│ test version: v4-test                                    │
│ change note: [________________________________]          │
│ prompt:                                                  │
│ [                                                ]       │
│ [Save Test Version] [Test Run] [Confirm Version] [Cancel]│
└──────────────────────────────────────────────────────────┘
```

검토 질문:

- prompt는 test version으로 저장한 뒤 테스트 후 confirmed version으로 승격한다.
- 이전 confirmed version rollback이 필요한가?

## 목업 승인 전 체크리스트

- [ ] Dashboard에서 처리해야 할 일이 바로 보이는가?
- [ ] Review 화면에서 기존 개념 목록과 신규 후보의 관계가 명확한가?
- [ ] batch 처리 중 실수 방지가 충분한가?
- [ ] `reject + retry instruction` 흐름이 자연스러운가?
- [ ] graph popup이 과하지 않고 필요한 정보만 보여주는가?
- [ ] prompt versioning이 Web Settings에 자연스럽게 들어가는가?
