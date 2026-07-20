# Phase 3 Page UX Spec — Inbox & Mapping Tasks

## Review status

- Status: `drafted_review_pending`
- Decision: 사용자가 직접 다룰 메뉴는 `Inbox`와 `Mapping` 두 축으로 단순화한다.
- Rationale: `normalize`, `chunk`, `embed`, `extract`, `link`, 내부 `map` 등은 대부분 자동 처리 과정이며 사용자가 매번 직접 컨트롤할 필요가 없다.

## 1. 페이지/메뉴 목적

사용자가 개입해야 하는 지점은 크게 두 곳이다.

```text
Inbox input → 자동 처리 pipeline → Mapping/New concept decision → Wiki
```

### Inbox

처리할 입력을 넣고, 처리 필요한 목록을 확인하는 곳.

포함:

- 사용자 파일 업로드
- 사용자 텍스트 입력
- `vault/00_Inbox/memo`, `files`, `text`에서 발견된 입력 목록
- 처리 시작
- 처리 상태 확인

### Mapping

자동 처리 이후 생성된 후보를 기존 wiki와 매핑하거나 신규 개념으로 처리하는 곳.

포함:

- 후보 목록
- LLM 평가 요약
- evidence/source link
- 기존 wiki 유사 항목
- merge / create new / edit / reject+retry

## 2. 메뉴 구조

권장 navigation:

```text
Dashboard | Inbox | Mapping | Vault | Wiki | Settings
```

기존 `Review / Mapping` 명칭은 길고 목적이 흐릴 수 있으므로, 최종 UI에서는 `Mapping` 또는 `Review` 중 하나로 줄인다.

추천:

- `Inbox`: 입력과 처리 시작
- `Mapping`: 처리 결과 후보 결정

## 3. 내부 자동 pipeline

`inbox → ingest → raw source` 이동만으로 mapping 후보가 생기는 것은 아니다. 후보는 source가 등록된 후 내부 처리 과정을 거쳐 생성된다.

단, 이 내부 단계들은 사용자가 일반적으로 직접 실행하지 않는다.

| Internal step | CLI/internal | 사용자에게 보이는 방식 | 후보 생성 여부 |
|---|---|---|---|
| Source input | upload/text/`00_Inbox` | Inbox 목록 | 아님 |
| Scan/Ingest | `inbox scan`, `ingest`, `ingest-text` | 처리 시작/처리 중 | source 등록 수준 |
| Raw save | internal/data write | source detail의 raw saved 상태 | 아님 |
| Normalize/Chunk/Embed | `normalize`, `chunk`, `embed` | 자동 처리 progress chip | 아님 |
| Extract/Link | `extract-claims`, `link` | 자동 처리 progress chip | claim/node/relation 후보 생성 |
| Map candidate generation | `map` | “mapping 후보 생성 중/완료” 상태 | mapping 후보 생성 |
| Human Mapping | Web Mapping | Mapping 페이지에서 사용자 결정 | 후보 소비/결정 |

핵심:

```text
Inbox = 입력과 처리 시작
Internal pipeline = 자동 처리
Mapping = 사람이 기존 wiki 연결/신규 개념을 결정
```

## 4. `map` 용어 정리

### 내부 `map`

- CLI 또는 내부 task: `wiki map <source_id>`
- 역할: 자동 처리 pipeline 안에서 기존 wiki와 비교할 mapping 후보를 생성한다.
- 사용자가 일반적으로 직접 누르는 메뉴가 아니다.

### Mapping 페이지

- 역할: 생성된 mapping 후보를 사람이 검토한다.
- 사용자가 여기서 결정한다:
  - 기존 wiki와 merge
  - 신규 개념 생성
  - 후보 수정
  - reject + retry instruction

한 줄 구분:

```text
internal map = 후보 생성
Mapping page = 후보 결정
```

## 5. PC-first 화면 구조

Inbox와 Mapping은 상단 메뉴에서 분리된 두 페이지로 두는 것을 권장한다.

### Inbox page

```text
┌──────────────────────────────────────────────────────────────┐
│ Inbox                                                        │
│ 📥 처리할 자료를 추가하고 자동 처리를 시작합니다.                │
├──────────────────────────────────────────────────────────────┤
│ Left: Source input list      │ Right: Selected source detail  │
│ - uploaded files             │ - file/text preview            │
│ - text notes                 │ - status chips                 │
│ - 00_Inbox detected items    │ - process button               │
├──────────────────────────────────────────────────────────────┤
│ Bottom/side: processing status queue                          │
└──────────────────────────────────────────────────────────────┘
```

### Mapping page

```text
┌──────────────────────────────────────────────────────────────┐
│ Mapping                                                      │
│ 🧭 처리 결과를 기존 wiki와 연결하거나 신규 개념으로 만듭니다.      │
├──────────────────────────────────────────────────────────────┤
│ Left: Candidate compact list │ Center: Candidate detail       │
│ - pending candidates         │ - LLM evaluation               │
│ - type/status chips          │ - evidence/source              │
│                              │ - proposed value               │
├──────────────────────────────┼───────────────────────────────┤
│ Right: Existing wiki match   │ Actions: Merge/Create/Retry    │
└──────────────────────────────────────────────────────────────┘
```

Tablet/Mobile:

- Inbox: source list → selected detail → processing status를 accordion으로 전환.
- Mapping: candidate list → detail → existing wiki match/action을 단계형 view로 전환.

## 6. Inbox에 보여줄 정보

### Source input list

- title/file name
- origin: upload / text / `00_Inbox/memo` / `00_Inbox/files` / `00_Inbox/text`
- status: new / processing / needs_mapping / completed / failed
- modified time
- duplicate warning
- processing chips:
  - raw saved
  - extracting
  - mapping ready
  - failed

### Source detail

- file path 또는 text title
- preview
- detected type
- current status
- raw source path, if created
- error summary, if failed

### Inbox actions

- `Upload file`
- `Add text`
- `Scan folder`
- `Process selected`
- `Open Mapping` when candidates are ready

숨길 것:

- 세부 CLI command
- raw JSON artifact
- source_id/job_id는 details 안에 표시

## 7. Mapping에 보여줄 정보

### Candidate compact list

- candidate title
- type: concept / claim / relation / mapping
- status: pending / retry / approved
- confidence or similarity chip
- source title

### Candidate detail

- LLM 평가 요약
- 어떤 신규 값인지
- evidence/source link
- proposed aliases/claims/relations
- raw candidate JSON은 details로 숨김

### Existing wiki match

- 유사 기존 wiki 목록
- 선택한 wiki 문서 preview
- 관계/aliases/claims 요약
- 1-hop relation preview는 Wiki 페이지와 연결 가능

### Mapping actions

- `Merge with selected wiki`
- `Create new concept`
- `Edit candidate`
- `Reject + retry`

## 8. 자동 처리 상태 표시

사용자가 중간 과정을 직접 누르지는 않지만, “무슨 일이 진행 중인지”는 보여줘야 한다.

표시 방식:

- progress chips
- short status row
- failed job alert
- `View technical details` 접힘 영역

예:

```text
raw saved ✓ · extracted ✓ · mapping ready ✓
```

실패 시:

```text
extract failed · Retry processing · View log
```

## 9. 필요한 API 초안

Inbox:

```text
GET  /api/inbox/items
POST /api/inbox/upload
POST /api/inbox/text
POST /api/inbox/scan
POST /api/inbox/process
GET  /api/inbox/items/{item_id}
```

Mapping:

```text
GET  /api/mapping/candidates
GET  /api/mapping/candidates/{candidate_id}
GET  /api/mapping/wiki-matches?candidate_id=...
POST /api/mapping/decide
```

Processing status:

```text
GET  /api/tasks/status
GET  /api/tasks/{task_id}
POST /api/tasks/{task_id}/retry
```

## 10. Empty / Error 상태

### Inbox empty

- message: “처리할 자료가 없습니다.”
- CTA: `Upload file`, `Add text`, `Scan folder`

### Inbox processing

- message: “자동 처리 중입니다.”
- CTA: `View status`

### Mapping empty

- message: “검토할 mapping 후보가 없습니다.”
- CTA: `Open Inbox`, `Scan folder`

### Processing failed

- message: “자동 처리 중 실패했습니다.”
- CTA: `Retry`, `View log`

## 11. 승인 기준

- 메뉴가 `Inbox`와 `Mapping` 두 축으로 이해된다.
- 중간 CLI 단계가 사용자가 일일이 실행해야 하는 것처럼 보이지 않는다.
- Inbox는 업로드/텍스트 입력/처리 필요한 목록에 집중한다.
- Mapping은 기존 wiki 매핑 또는 신규 개념 처리에 집중한다.
- 내부 `map`과 Mapping 페이지의 차이가 문구와 UX에서 명확하다.
- PC 기본 화면에서 정보량이 충분하고, 모바일/태블릿에서는 단계형으로 접힌다.
