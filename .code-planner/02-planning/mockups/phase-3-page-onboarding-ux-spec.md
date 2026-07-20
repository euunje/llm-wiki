# Phase 3 Page UX Spec — Onboarding / Setup

## Review status

- Status: `drafted_review_pending`
- Review process: 페이지별 대화 검토 후 필요한 질의/응답을 반영해 문서를 업데이트한다.
- PRV note: 기존 초안 PRV가 열렸더라도 최종 승인은 아니다. 전체 페이지 UX spec/mockup이 정리된 뒤 최종 PRV에서 한 번에 리뷰한다.

## User decisions applied

- Onboarding first screen: **A — Wizard step rail 중심**
- API key storage: **A — `.env`에 자동 저장**
- File browser start: **B — 홈 디렉터리부터 시작 + 상위 이동 가능**
- Embedding model policy: **fastembed 제공 모델을 사용한다. 특정 모델 경로/목록에서 embedding 모델 목록을 불러와 선택하고, 필요 시 다운로드 경로를 제공한다.**
- File browser hidden/unauthorized policy: **숨김 처리한다.**

## Global UX constraints applied

- PC-first layout이 기본이다.
- Tablet/Mobile에서도 조회와 기본 설정 흐름이 깨지지 않아야 한다.
- 디자인은 아이콘 + 짧은 label + 1줄 helper text 중심으로 구성한다.
- 긴 설명 문단은 피하고, 필요 시 help drawer/details로 숨긴다.

## 1. 페이지 목적

Onboarding은 사용자가 처음 실행하거나 설정을 다시 잡을 때, 기술 설정 파일을 직접 만지지 않고 다음을 끝내는 페이지다.

1. LLM provider 연결
2. 사용할 모델 선택
3. Vault 신규/기존 선택
4. 전체 경로 file browser로 경로 선택
5. 기존 vault mapping
6. Inbox input → 자동 처리 → Mapping/Wiki 흐름 이해 및 준비 상태 확인

## 2. 핵심 UX 원칙

- 사용자는 `settings.yaml`, `.env`, DB 구조를 몰라도 된다.
- 한 화면에 모든 form을 펼치지 않는다.
- wizard step 단위로 현재 해야 할 일만 보여준다.
- 설정값 저장 후 민감정보(API key)는 다시 보여주지 않는다.
- 연결 테스트와 모델 목록 조회는 사용자의 다음 행동을 결정하게 해주는 핵심 기능이다.
- Vault 경로는 전체 OS 경로 탐색을 허용하되, 선택 후 위험/권한/구조 상태를 명확히 알려준다.
- File browser는 홈 디렉터리에서 시작하고, 사용자가 상위 경로로 이동할 수 있다.
- API key는 `.env`에 자동 저장하고, UI/API 응답에는 값이 다시 나오지 않는다.

## 3. 화면 구조

PC 기본 구조:

```text
┌──────────────────────────────────────────────────────────────┐
│ Onboarding / Setup                                            │
│ 짧은 subtitle + 상태 chip                                      │
├──────────────────────────────────────────────────────────────┤
│ Icon step rail     │ Step body                                │
│ 🔌 LLM             │ 선택된 step의 상세 설정                   │
│ 🧪 Test            │                                          │
│ 🧠 Models          │                                          │
│ 📁 Vault           │                                          │
│ 📥 Inbox/Mapping   │                                          │
│ ✅ Finish          │                                          │
├──────────────────────────────────────────────────────────────┤
│ 하단: Back / Save / Next                                      │
└──────────────────────────────────────────────────────────────┘
```

Tablet/Mobile 구조:

```text
┌──────────────────────────────┐
│ Onboarding + status chip      │
├──────────────────────────────┤
│ Horizontal step chips          │
│ 🔌 LLM · 🧪 Test · 🧠 Models... │
├──────────────────────────────┤
│ Current step body              │
├──────────────────────────────┤
│ Sticky bottom CTA              │
└──────────────────────────────────────────────────────────────┘
```

## 4. Step별 상세

### Step 1 — LLM Provider

사용자 목표: 내가 사용하는 LLM 런타임을 선택한다.

UI:

- Provider dropdown/cards
  - Ollama
  - LM Studio
  - Custom OpenAI-compatible
- 선택 시 endpoint 기본값 자동 제안
  - Ollama: `http://127.0.0.1:11434`
  - LM Studio: `http://127.0.0.1:1234/v1`
  - Custom: 빈 값
- Endpoint input
- API key password input
  - Ollama은 optional
  - LM Studio/Custom은 optional 또는 required 여부를 provider rule로 표시
- 저장 정책 안내:
  - 입력 후 `.env`에 바로 저장
  - 화면에 다시 표시하지 않음
  - 상태만 `configured / missing` 표시

Actions:

- `Save connection`
- `Test connection`

### Step 2 — Connection Test

사용자 목표: 실제로 endpoint/API key가 동작하는지 확인한다.

UI:

- Test result card
  - Provider
  - Endpoint
  - API key: configured/missing only
  - Connection: success/fail
  - Error message, if failed
- 실패 시 provider별 해결 힌트
  - Ollama: Ollama 앱/서버 실행 여부
  - LM Studio: local server started 여부
  - Custom: endpoint `/v1/models` 호환 여부

Actions:

- `Run test again`
- `Back to provider settings`

### Step 3 — Model Select

사용자 목표: 연결된 LLM에서 사용할 chat 모델과, fastembed 기반 embedding 모델을 선택한다.

UI:

- Chat model 영역
  - `Refresh provider model list`
  - Provider/Ollama/LM Studio에서 가져온 모델 목록
  - model name
  - inferred capability: chat / unknown
  - selected for: default chat
- Embedding model 영역
  - `Load fastembed model list`
  - 특정 모델 목록/경로에서 fastembed 지원 모델을 불러옴
  - model name
  - language/support hint
  - local availability: downloaded / not downloaded
  - download path 또는 cache path 표시
  - selected for: default embedding
- 모델이 없을 때:
  - Ollama: `ollama pull ...` 안내
  - LM Studio: 모델 load 안내
  - Custom: `/models` 응답 확인 안내
  - fastembed: model list source/download path 확인 안내

Actions:

- `Use as chat model`
- `Use as embedding model`
- `Download embedding model`
- `Continue`

### Step 4 — Vault Setup

사용자 목표: 신규 vault를 만들지, 기존 vault를 연결할지 선택한다.

UI:

- Mode segmented control
  - New vault
  - Existing vault
- 전체 경로 picker
  - current path
  - 홈 디렉터리에서 시작
  - parent 이동 허용
  - folder list
  - manual path input
  - hidden folder와 권한 없는 folder는 기본 숨김 처리
- New vault mode:
  - 선택 경로에 기본 구조 생성 예정 표시
  - `vault/00_Inbox`, `10_Wiki`, `20_Review`, `80_Raws`, `90_Settings`
- Existing vault mode:
  - 구조 감지 결과 표시
  - missing folders 표시
  - mapping UI로 이동

Actions:

- `Browse`
- `Use selected folder`
- `Create missing folders`

### Step 5 — Existing Vault Mapping

사용자 목표: 기존 vault의 폴더를 시스템 역할에 매핑한다.

UI:

```text
System role                    Selected folder
Inbox memo/text/files           [select folder]
Wiki concepts/pages/sources     [select folder]
Review candidates/mapping       [select folder]
Raw index                       [select folder]
Settings prompts/templates      [select folder]
```

기본 추천 mapping:

- `vault/00_Inbox/memo`
- `vault/00_Inbox/files`
- `vault/00_Inbox/text`
- `vault/10_Wiki/concepts`
- `vault/10_Wiki/pages`
- `vault/10_Wiki/sources`
- `vault/20_Review/candidates`
- `vault/20_Review/mapping`
- `vault/80_Raws`
- `vault/90_Settings/prompts`

Actions:

- `Auto-detect`
- `Save mapping`
- `Create missing folders`

### Step 6 — Inbox / Mapping Pipeline

사용자 목표: 입력 자료를 어디에 넣고, 자동 처리 후 어디에서 매핑 결정을 하는지 이해한다.

UI:

```text
Inbox input           Automatic pipeline          Mapping / Wiki
00_Inbox/memo    →    ingest/extract/map      →   mapping candidates
00_Inbox/files   →    ingest/extract/map      →   mapping candidates
00_Inbox/text    →    ingest-text/extract/map →   mapping candidates
```

표시 정보:

- Inbox folder status
- new/unprocessed item count
- last scan time
- next action: `Open Inbox`, `Open Mapping`

### Step 7 — Finish

사용자 목표: 현재 설정이 충분한지 확인하고 다음 페이지로 이동한다.

UI:

- Checklist
  - LLM provider selected
  - connection test passed
  - chat model selected
  - embedding model selected or explicitly skipped
  - vault path selected
  - source input/workflow mapping ready
- CTA
  - `Open Inbox`
  - `Open Mapping`
  - `Open Vault Browser`
  - `Go to Dashboard`

## 5. 필요한 API 초안

```text
GET  /api/setup/status
POST /api/setup/llm/connection
POST /api/setup/llm/test
GET  /api/setup/llm/models
POST /api/setup/llm/models/select

GET  /api/setup/fs/browse?path=...
POST /api/setup/vault/select
POST /api/setup/vault/mapping
POST /api/setup/vault/create-missing

GET  /api/setup/inbox/status
POST /api/setup/inbox/scan
```

## 6. 민감정보 정책

- API key는 password input으로 입력한다.
- 저장 후 input은 즉시 비운다.
- 이후 status에서는 `api_key_configured: true/false`만 반환한다.
- key 원문은 API response, HTML, JS state, log에 남기지 않는다.
- 저장 위치는 `.env` 자동 저장으로 확정한다.
- `.env`는 source control에 포함하지 않는다.

## 7. Empty / Error 상태

- LLM server offline
- provider endpoint invalid
- model list empty
- selected vault path permission denied
- selected folder not found
- existing vault mapping incomplete
- inbox folders missing

각 오류는 다음 action을 함께 표시한다.

## 8. 승인 기준

- 사용자가 Onboarding만 보고 LLM 연결과 Vault 선택을 완료할 수 있다.
- API key 값이 다시 보이지 않는다.
- 전체 경로 선택이 가능하다.
- 기존 vault mapping이 명확하다.
- `Inbox input → 자동 처리 → Mapping/Wiki` 흐름이 화면에서 이해된다.
- 다음 행동이 `Open Inbox`, `Open Mapping`, `Open Vault Browser`, `Dashboard` 중 하나로 명확하다.

## 9. 구현 전 열린 질문

1. fastembed 모델 목록을 가져올 기본 source/path를 무엇으로 둘지?
2. embedding model download/cache 경로 기본값을 어디로 둘지?
