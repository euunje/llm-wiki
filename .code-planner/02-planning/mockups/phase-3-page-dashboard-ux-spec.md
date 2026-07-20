# Phase 3 Page UX Spec — Dashboard

## Review status

- Status: `drafted_review_pending`
- Scope: Dashboard overview composition
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- 상단 metric card는 `Inbox / Mapping / Wiki / Vault / Issues` 5개로 확정한다.
- 1차 Dashboard에서는 CPU/RAM 같은 OS 자원 사용량은 제외한다.
- System usage는 LLM/DB/Vault/task 상태 중심으로 표시한다.

## 1. 페이지 목적

Dashboard는 사용자가 현재 시스템 상태와 다음 행동을 한눈에 파악하는 첫 화면이다.

Dashboard에서 보여야 하는 핵심:

- Inbox 수량
- Mapping/new wiki 처리 대기
- Vault/Wiki 현황
- 시스템 사용 현황
- Error/Issues
- 최근 처리 결과
- 다음 행동 CTA

## 2. PC 기본 화면 구조

```text
┌──────────────────────────────────────────────────────────────┐
│ Dashboard                                                    │
│ 오늘 처리할 항목과 시스템 상태를 확인합니다.                    │
├──────────────────────────────────────────────────────────────┤
│ Top metric cards                                             │
│ [Inbox] [Mapping] [Wiki] [Errors] [System]                   │
├──────────────────────────────────────────────────────────────┤
│ Left: Needs attention        │ Right: System usage/status     │
│ - failed items               │ - LLM connection               │
│ - mapping pending            │ - Vault path/read status       │
│ - new wiki candidates        │ - disk/db/task status          │
├──────────────────────────────────────────────────────────────┤
│ Bottom: Recent activity / completed records                   │
└──────────────────────────────────────────────────────────────┘
```

## 3. 상단 Metric cards

상단에는 사용자가 가장 먼저 판단해야 하는 수량을 표시한다.

### Inbox card

표시:

- new
- processing
- failed

예:

```text
📥 Inbox
New 4 · Processing 2 · Failed 1
[Open Inbox]
```

### Mapping card

표시:

- new mapping candidates
- in progress wizard
- error/retry needed

예:

```text
🧭 Mapping
New 3 · In review 1 · Errors 1
[Open Mapping]
```

### Wiki card

표시:

- total wiki pages/concepts
- newly created wiki count
- recently updated count

예:

```text
📚 Wiki
142 pages · New 3 · Updated 8
[Open Wiki]
```

### Vault card

표시:

- vault path status
- readable/unreadable
- folder mapping ok/missing

예:

```text
📁 Vault
Ready · 5 root folders
[Open Vault]
```

### Errors/System card

표시:

- total issues
- LLM status
- DB status
- task queue health

예:

```text
⚠️ Issues
4 need attention
[Review issues]
```

## 4. Needs attention 영역

목적: 사용자가 지금 처리해야 하는 항목을 모아 보여준다.

우선순위:

1. errors / failed
2. mapping pending
3. inbox new
4. system setup warning

표시 예:

```text
Needs attention

⚠️ Inbox processing failed       paper-rag.md       [Open]
🧭 Mapping new candidates        3 items            [Open]
🔌 LLM connection warning        API key missing    [Fix]
📁 Vault read warning            80_Raws unreadable [Open]
```

각 row는 원인 페이지로 이동한다.

연결:

- Inbox failed → Inbox item detail
- Mapping pending/error → Mapping candidate/오류 탭
- LLM warning → Settings LLM
- Vault warning → Vault Browser or Onboarding Vault
- Wiki render/graph issue → Wiki document

## 5. System usage/status 영역

목적: 시스템이 정상 작동 가능한지 확인한다.

표시:

- LLM provider
- selected chat model
- selected embedding model
- concurrent LLM tasks
- DB status
- Vault path
- data path
- last inbox scan
- last successful mapping

예:

```text
System

LLM: Ollama · llama3.1:8b · OK
Embedding: fastembed MiniLM · downloaded
Concurrency: 1 task
Vault: /home/eunjae/vault/llm-wiki · readable
DB: OK
Last scan: 12:30
```

CTA:

- `Test LLM`
- `Open Settings`
- `Open Vault`

## 6. Recent activity / completed records

목적: 최근에 무엇이 처리됐는지 확인한다.

표시:

- completed inbox item
- created wiki
- merged mapping
- rejected/retry
- prompt rollback/confirm
- route/model change

예:

```text
Recent activity

✅ Agentic RAG created          from paper-agentic-rag.md
🔗 RAG → Vector Search confirmed
↩️ map prompt rolled back to phase2-default-v1
⚙️ Relationship 검증 model changed to mistral:7b
```

각 row는 관련 record/detail로 이동한다.

## 7. 모바일/태블릿 구조

Tablet:

- metric cards 2-column
- needs attention 먼저
- system status 아래

Mobile:

```text
Dashboard
Metric cards carousel/stack
Needs attention
System status accordion
Recent activity
```

모바일에서는 `Needs attention`을 metric 다음에 바로 둔다.

## 8. Empty/Good 상태

### All clear

```text
모든 항목이 정상입니다.
[Open Inbox] [Open Wiki]
```

### No data yet

```text
아직 처리된 자료가 없습니다.
[Open Inbox] [Upload file] [Add text]
```

### Setup incomplete

```text
LLM 또는 Vault 설정이 필요합니다.
[Open Onboarding]
```

## 9. 필요한 API 초안

```text
GET /api/dashboard/summary
GET /api/dashboard/needs-attention
GET /api/dashboard/system-status
GET /api/dashboard/recent-activity
```

summary 포함:

- inbox counts
- mapping counts
- wiki counts
- vault status
- issue counts
- system status

## 10. 승인 기준

- Inbox 수량이 보인다.
- Mapping/new wiki 처리 대기가 보인다.
- Vault/Wiki 현황이 보인다.
- 시스템 사용 현황이 보인다.
- Error/Issues가 보이고 각 원인 페이지로 이동한다.
- 최근 처리 결과를 볼 수 있다.
- PC에서 한 화면 요약이 가능하다.
- 모바일에서 Needs attention이 우선 노출된다.

## 11. 확인 필요

- 현재 없음. Dashboard UX는 임시 확정 상태로 최종 mockup/review 단계로 넘어갈 수 있다.
