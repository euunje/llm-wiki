# Phase 3 Page UX Spec — Settings: LLM / Models / Routes

## Review status

- Status: `drafted_review_pending`
- Scope: Settings LLM/model/route UX clarification
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## 문제

현재 Settings의 `Save route` 기능은 의미가 명확하지 않다.

사용자 입장에서는 다음이 불분명하다.

- route가 무엇인지
- 왜 작업별 모델을 나눠야 하는지
- model 설정이 안 된 상태에서 route를 저장할 수 있는지
- Onboarding의 LLM 설정과 Settings의 LLM 설정이 어떻게 다른지

## User decisions applied

- Onboarding과 Settings의 기본 LLM 설정 화면은 동일한 구조를 사용한다.
- Settings는 Onboarding 이후에도 같은 방식으로 provider/endpoint/API key/model을 수정할 수 있어야 한다.
- Route는 기본 설정이 아니라 **고급 설정 옵션**으로 둔다.
- 기본 route 정책은 모든 chat 작업이 같은 기본 chat model을 사용한다.
- 필요할 때만 같은 endpoint에서 지원하는 다른 model을 작업별로 선택한다.
- LLM 동시 작업은 기본 1개, 고급 옵션에서 최대 3개까지 허용한다.
- 동시 작업 증가는 시스템/로컬 LLM 서버에 부하가 될 수 있으므로 경고와 제한이 필요하다.
- Advanced route row button label: `Use this model`.

## 1. Onboarding과 Settings 역할 분리

### Onboarding

목적: 처음 사용할 수 있게 연결을 완성한다.

담당:

- provider 선택: Ollama / LM Studio / Custom
- endpoint 입력
- API key 입력 후 `.env` 저장
- 연결 테스트
- chat model 선택
- fastembed embedding model 선택/download
- Vault 경로 선택

한 줄 정의:

```text
Onboarding = 처음 연결하고 작동하게 만드는 곳
```

### Settings — LLM / Models / Routes

목적: Onboarding과 동일한 방식으로 LLM/model 기본 설정을 확인·수정하고, 필요 시 고급 설정에서 작업별 사용할 모델을 관리한다.

담당:

- provider/endpoint/API key configured 상태 확인
- 연결 재테스트
- 모델 목록 refresh
- model registry 확인/편집
- chat model / embedding model 상태 확인
- 고급 옵션: 작업별 route 설정
- 고급 옵션: LLM 동시 작업 수 설정
- route 변경 이력 확인

한 줄 정의:

```text
Settings = 기본 연결 설정을 유지관리하고, 필요 시 고급 모델/route 옵션을 조정하는 곳
```

## 2. Route의 의미

Route는 고급 설정이며, “작업별 사용할 모델 선택”이다.

기본 사용자는 route를 설정할 필요가 없다. 모든 chat 작업은 기본 chat model을 사용한다.

예:

```text
Page 검증          → chat model A
Page Mapping       → chat model A
Relationship 검증  → chat model B
Retry instruction  → chat model A
Embedding/Search   → fastembed embedding model
```

사용자에게 보이는 설명:

```text
Advanced route는 각 작업에서 사용할 모델을 따로 정하는 설정입니다.
대부분의 경우 기본 모델 하나를 그대로 사용하면 됩니다.
같은 endpoint에서 여러 모델을 지원할 때만 작업별로 모델을 나눠 선택하세요.
```

## 2-1. LLM 동시 작업 옵션

기본은 한 번에 1개 작업만 실행한다.

고급 옵션에서 최대 3개까지 동시 작업 수를 늘릴 수 있다.

```text
Concurrent LLM tasks
(•) 1 — 기본, 안정적
( ) 2 — 빠르지만 로컬 모델 부하 증가
( ) 3 — 고급, 충분한 GPU/메모리 필요
```

부하 영향:

- Ollama/LM Studio/local model은 동시 요청이 늘면 VRAM/RAM/CPU 사용량이 증가한다.
- 모델이 크면 2~3개 동시 작업에서 timeout 또는 응답 지연이 발생할 수 있다.
- embedding 작업과 chat 작업이 동시에 돌면 디스크/cache/CPU 부하가 늘 수 있다.

정책:

- 기본값: `1`
- UI 최대값: `3`
- 2 이상 선택 시 경고 표시
- 처리 실패/timeout 증가 시 다시 1로 낮추라는 안내 제공
- provider가 동시 요청을 지원하지 않으면 1로 강제

## 3. PC 기본 화면 구조

Settings는 좌측 tab 구조를 유지한다.

```text
┌──────────────────────────────────────────────────────────────┐
│ Settings                                                     │
├───────────────┬──────────────────────────────────────────────┤
│ LLM           │ LLM / Models / Routes                        │
│ Prompt        │                                              │
│ Vault         │ 1. Basic LLM setup                           │
│ Auth          │ 2. Model registry                            │
│               │ 3. Advanced options                          │
│               │    - task routes                             │
│               │    - concurrent tasks                        │
│               │ 4. Change history                            │
└───────────────┴──────────────────────────────────────────────┘
```

## 4. Section 1 — Basic LLM setup

목적: Onboarding과 동일한 구조로 LLM 연결을 확인/수정한다.

표시:

- provider
- endpoint
- API key: configured / missing only
- connection test status
- last tested time
- selected chat model
- selected embedding model

Actions:

- `Test connection`
- `Refresh models`
- `Save basic settings`

주의:

- API key 값은 표시하지 않음
- API key 변경은 Settings에서도 가능하지만 password input은 저장 후 즉시 비움

## 5. Section 2 — Model registry

목적: 사용 가능한 모델 목록과 각 모델의 역할을 보여준다.

표시:

```text
Chat models
llama3.1:8b          available   default
mistral:7b           available

Embedding models
paraphrase-multilingual-MiniLM-L12-v2   downloaded   default
bge-small-en-v1.5                       not downloaded
```

Actions:

- `Refresh provider models`
- `Load fastembed models`
- `Download embedding model`
- `Set default chat`
- `Set default embedding`

Onboarding 대비 부족했던 부분:

- Settings에서도 model registry를 확인/수정할 수 있어야 한다.
- route save 전에 모델 설정 가능 상태가 보여야 한다.
- fastembed embedding model은 provider model과 분리해서 보여야 한다.

## 6. Section 3 — Advanced options

기본적으로 접혀 있다.

```text
Advanced options
작업별 모델 분리와 동시 처리 수를 조정합니다.
대부분의 사용자는 변경하지 않아도 됩니다.
```

### 6-1. Concurrent LLM tasks

표시:

```text
Concurrent LLM tasks
[1 안정적] [2 빠름] [3 고급]
```

2 또는 3 선택 시 경고:

```text
동시 작업 수를 늘리면 로컬 LLM 서버, GPU/메모리 사용량이 증가할 수 있습니다.
오류나 timeout이 늘면 1로 낮추세요.
```

### 6-2. Task routes

목적: 작업별 사용할 모델을 선택한다.

기본은 모든 chat 작업이 default chat model을 사용한다. route table은 advanced option을 연 경우에만 보인다.

Route row 예:

```text
Task                         Model                  Status
Page 검증                    llama3.1:8b             default
Page Mapping                 llama3.1:8b             default
Relationship 검증            mistral:7b              custom
Retry instruction            llama3.1:8b             default
Embedding/Search             paraphrase-MiniLM       embedding
```

각 row 표시:

- task icon
- task name
- short description
- current model
- model select dropdown
- status chip: default / custom / invalid / missing
- `Save` button

`Save route` 버튼 문구는 단독으로 쓰지 않는다.

권장 문구:

```text
Save model for this task
```

또는 row별:

```text
Use this model
```

## 7. Route save 활성/비활성 규칙

route save는 모델 설정이 충분할 때만 가능하다.

비활성 조건:

- provider connection missing
- selected model missing
- selected model capability mismatch
- selected model is not available from the same configured endpoint
- embedding task에 chat model 선택
- chat task에 embedding model 선택

비활성 표시 예:

```text
Save disabled: select a chat model first
```

활성 조건:

- 해당 task capability에 맞는 model이 선택됨
- model이 available/downloaded 상태

## 8. Route task 목록

Phase 3 UX 기준 route task는 사용자 언어로 표시한다.

내부 task id는 details에 숨긴다.

권장 task:

| User label | Internal task | Required capability |
|---|---|---|
| Page 검증 | `page_validate` | chat |
| Page Mapping | `page_mapping` | chat |
| Relationship 검증 | `relationship_validate` | chat |
| Retry instruction | `retry_instruction` | chat |
| Prompt test | `prompt_test` | chat |
| Embedding/Search | `embedding` | embedding |

기존 CLI task와 다르면 Build에서 route mapping adapter를 둔다.

## 9. Section 4 — Change history

목적: 모델/route 변경 기록을 확인한다.

표시:

- changed at
- changed setting
- previous model
- new model
- changed by: admin/web

예:

```text
2026-07-19 10:30  Relationship 검증  llama3.1:8b → mistral:7b
```

## 10. Empty/Error 상태

### No provider configured

```text
LLM provider가 설정되지 않았습니다.
[Open Onboarding setup]
```

### No models found

```text
사용 가능한 chat model이 없습니다.
[Refresh models] [Open Onboarding setup]
```

### Embedding model missing

```text
Embedding model이 선택되지 않았습니다.
[Load fastembed models]
```

### Invalid route

```text
이 작업에는 chat model이 필요합니다.
embedding model은 선택할 수 없습니다.
```

## 11. 필요한 API 초안

```text
GET  /api/settings/llm/status
POST /api/settings/llm/test
GET  /api/settings/models/provider
GET  /api/settings/models/fastembed
POST /api/settings/models/download
POST /api/settings/models/default
GET  /api/settings/routes
POST /api/settings/routes
GET  /api/settings/routes/history
GET  /api/settings/llm/concurrency
POST /api/settings/llm/concurrency
```

## 12. 승인 기준

- Onboarding과 Settings의 역할 차이가 명확하다.
- Onboarding과 Settings의 기본 LLM 설정 UI가 동일한 구조를 가진다.
- route가 고급 설정이며 “작업별 사용할 모델 선택”임을 사용자가 이해한다.
- 기본은 모든 작업이 같은 기본 chat model을 사용한다.
- 모델 설정이 부족한 상태에서는 route save가 비활성화된다.
- chat model과 embedding model이 분리되어 보인다.
- fastembed embedding model 목록/다운로드 상태가 보인다.
- `Save route`라는 모호한 버튼 대신 `Use this model` 또는 `Save model for this task`가 보인다.
- LLM 동시 작업 수는 기본 1, 최대 3으로 제한된다.
- 2 이상 선택 시 부하 경고가 보인다.
- route 변경 이력이 보인다.

## 13. 확인 필요

- 현재 없음. Settings LLM/Models/Routes UX는 임시 확정 상태로 다음 페이지 검토로 넘어갈 수 있다.
