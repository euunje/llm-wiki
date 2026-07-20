# Phase 3 Web UI — A/B Wireframes before Fix

## 확정된 사용자 결정

1. Settings에서 직접 변경 가능한 범위
   - Prompt 설정/버전 관리
   - LLM 설정
   - Vault 폴더 변경은 Onboarding/Setup 흐름에서 처리
2. 첫 접속 흐름
   - 최초 접속/환경 미설정 시 Onboarding으로 진입
   - Onboarding에서 `.env` setup 상태를 안내
3. 화면 구조
   - A안과 B안을 텍스트 목업으로 비교 후 사용자가 선택

---

# A안 — 상단 메뉴 + 화면별 2~3 Column

## 전체 구조

```text
┌─────────────────────────────────────────────────────────────┐
│ LLM Wiki Local | Onboarding | Dashboard | Wiki | Review/Mapping | Settings | Logout │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Page Title                                      Primary CTA  │
│ 한 줄 설명 / 현재 상태 hint                                  │
├─────────────────────────────────────────────────────────────┤
│ 화면별 content grid                                          │
└─────────────────────────────────────────────────────────────┘
```

## Onboarding

```text
Onboarding / Setup
┌──────────────────────────────┬──────────────────────────────┐
│ Setup Checklist              │ Next Actions                  │
│ [ ] .env password configured │ 1. Web password 설정          │
│ [ ] LLM endpoint configured  │ 2. LLM endpoint/model 입력    │
│ [ ] Vault path selected      │ 3. Vault folder 확인/변경     │
│ [ ] DB/schema ready          │ 4. CLI ingest 또는 Wiki 보기  │
│ [ ] candidate/wiki exists    │                              │
└──────────────────────────────┴──────────────────────────────┘
```

## Dashboard

```text
Dashboard
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ 승인필요 │ Pending  │ 오류     │ Wiki수   │ DB       │ System   │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
┌──────────────────────────────┬──────────────────────────────┐
│ Recent Jobs / Errors         │ Review Queue Summary          │
│ - failed/queued/running      │ - mapping/node/relation count │
│ - retry target               │ - review_route breakdown      │
└──────────────────────────────┴──────────────────────────────┘
```

## Wiki

```text
Wiki
┌──────────────────────┬──────────────────────────────────────┐
│ Search + Wiki List   │ Selected Wiki Detail                  │
│ - concept/page list  │ - title / aliases                     │
│ - source/path        │ - meaning / claims / relations        │
│ - filters            │ - markdown preview                    │
└──────────────────────┴──────────────────────────────────────┘
```

## Review / Mapping

```text
Review / Mapping
┌────────────────────┬────────────────────────────┬────────────────────┐
│ Existing Wiki List │ Selected Wiki / Mapping    │ Candidate Batch    │
│ similarity/mapping │ meaning/aliases/claims     │ node/mapping cards │
│ targets            │ relations/compile preview  │ merge/new/edit     │
│                    │ graph button               │ reject+retry       │
└────────────────────┴────────────────────────────┴────────────────────┘
```

## Settings

```text
Settings
┌──────────────────────────────┬──────────────────────────────┐
│ LLM / Model Settings         │ Prompt Versioning             │
│ - endpoint configured?       │ - task list                   │
│ - model list                 │ - confirmed/test version      │
│ - route mapping editable     │ - save test                   │
│ - env key masked             │ - test run / confirm          │
└──────────────────────────────┴──────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Vault Folder Setup                                            │
│ - current vault path / data path / change via onboarding flow │
└─────────────────────────────────────────────────────────────┘
```

## 장점

- 기존 목업과 가장 유사하다.
- 화면이 단순하고 구현 위험이 낮다.
- Review 3-column 구조가 명확하다.

## 단점

- 메뉴가 많아지면 상단이 복잡해질 수 있다.
- 설정/운영 기능이 커지면 화면별 depth가 부족할 수 있다.

---

# B안 — 왼쪽 Sidebar 고정 + 본문

## 전체 구조

```text
┌───────────────┬─────────────────────────────────────────────┐
│ LLM Wiki      │ Page Title                         CTA      │
│               ├─────────────────────────────────────────────┤
│ Onboarding    │                                             │
│ Dashboard     │ Main Content                                │
│ Wiki          │                                             │
│ Review/Mapping│                                             │
│ Settings      │                                             │
│               │                                             │
│ Logout        │                                             │
└───────────────┴─────────────────────────────────────────────┘
```

## Onboarding

```text
Sidebar: Onboarding active
Main:
┌─────────────────────────────────────────────────────────────┐
│ Setup Progress: 3/6                                          │
├──────────────────────┬──────────────────────┬───────────────┤
│ Env                  │ LLM                  │ Vault         │
│ password/key status  │ endpoint/model route │ folder change │
├──────────────────────┴──────────────────────┴───────────────┤
│ Recommended next step / CLI command / Continue button        │
└─────────────────────────────────────────────────────────────┘
```

## Dashboard

```text
Sidebar: Dashboard active
Main:
┌──────────┬──────────┬──────────┬──────────┐
│ Review   │ Jobs     │ Errors   │ System   │
└──────────┴──────────┴──────────┴──────────┘
┌──────────────────────────────┬──────────────────────────────┐
│ Job/Error Timeline           │ Review Queue / Mapping 상태   │
└──────────────────────────────┴──────────────────────────────┘
```

## Wiki

```text
Sidebar: Wiki active
Main:
┌──────────────┬───────────────────────────────────────────────┐
│ Wiki browser │ Detail                                        │
│ search/filter│ markdown / aliases / claims / relations       │
└──────────────┴───────────────────────────────────────────────┘
```

## Review / Mapping

```text
Sidebar: Review/Mapping active
Main:
┌──────────────┬──────────────────────────────┬────────────────┐
│ Similar Wiki │ Selected Wiki + Graph/Preview│ Candidate Batch│
└──────────────┴──────────────────────────────┴────────────────┘
```

## Settings

```text
Sidebar: Settings active
Main:
┌──────────────┬───────────────────────────────────────────────┐
│ Settings tabs│ Selected Settings Panel                       │
│ - LLM        │ LLM: endpoint/model/route/key status          │
│ - Prompt     │ Prompt: test/confirm/history                  │
│ - Vault      │ Vault: current path/change through setup      │
│ - Auth       │ Auth: password configured, no value exposure   │
└──────────────┴───────────────────────────────────────────────┘
```

## 장점

- PC 기반 운영 도구 느낌이 강하다.
- 메뉴가 많아져도 구조가 안정적이다.
- Settings처럼 기능이 많은 화면을 tabs/section으로 확장하기 쉽다.

## 단점

- 기존 승인 목업의 상단 nav 구조와 차이가 크다.
- 모바일에서는 sidebar collapse 처리가 필요하다.
- 구현량이 A안보다 많다.

---

# 추천

현재 프로젝트 목적은 PC 기반의 개인 운영 도구이고, 앞으로 Wiki/Mapping/Settings가 커질 가능성이 높다.

따라서 추천은 **B안**이다.

단, 기존 승인 목업과의 일관성 및 빠른 fix를 우선하면 **A안**이 안전하다.

## 선택 기준

- 빠른 수습과 목업 연속성 우선: A안
- PC 운영 도구로 장기 확장성 우선: B안

## 사용자 선택

- 선택: **3안 — A안 기반 + Settings만 B안식 좌측 탭 구조**

확정 방향:

- 전체 앱 navigation은 A안처럼 상단 메뉴를 유지한다.
- 메뉴 순서:

```text
Onboarding | Dashboard | Wiki | Review / Mapping | Settings | Logout
```

- 화면별 기본 구조는 A안의 page title + hint + toolbar + 2~3 column grid를 따른다.
- 단, Settings 화면은 기능이 많으므로 B안처럼 내부 좌측 탭/섹션 목록을 둔다.

Settings 내부 구조:

```text
Settings
┌──────────────┬───────────────────────────────────────────────┐
│ Settings tabs│ Selected Settings Panel                       │
│ - LLM        │ LLM endpoint/model/route/key status + edit    │
│ - Prompt     │ Prompt test/confirm/history                   │
│ - Vault      │ Vault folder status/change via onboarding     │
│ - Auth       │ Web password configured status, no value leak  │
└──────────────┴───────────────────────────────────────────────┘
```

이 선택의 의도:

- 기존 승인 목업과 큰 틀은 유지한다.
- PC-first 화면에서 Dashboard/Wiki/Review는 빠르게 복구한다.
- Settings는 실기능이 많으므로 좌측 탭 구조로 명확히 분리한다.
- 모바일은 보조 접근으로, Settings 편집과 Review batch 작업은 PC 중심으로 검증한다.
