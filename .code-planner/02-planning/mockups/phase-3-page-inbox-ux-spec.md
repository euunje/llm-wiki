# Phase 3 Page UX Spec — Inbox

## Review status

- Status: `drafted_review_pending`
- Scope: Inbox 화면 구성 fix
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- 기본 정렬: `failed → needs_mapping → new → processing → completed`
- Upload UX: PC는 drag & drop zone + 버튼, 모바일은 버튼 중심
- Completed 항목: list에는 남기되 아래로 정렬하고 filter로 접근. 주 용도는 완료 기록/결과 감사 확인
- Processing 항목: 진행 로그 확인 기능 필요
- Completed 의미: 처리 완료 이력과 결과를 확인하는 기록 상태. 스키마에 저장된 기반으로 어떤 모델이 어떤 결과를 만들었는지 확인할 수 있어야 함
- Raw LLM response / schema JSON / CLI log: 기본 숨김, details에서만 확인

## 1. 페이지 목적

Inbox는 사용자가 처리할 자료를 넣고, 처리 필요한 목록을 확인하고, 자동 처리 pipeline을 시작하는 화면이다.

사용자가 이 페이지에서 해야 하는 일:

1. 파일 업로드
2. 텍스트 직접 입력
3. `vault/00_Inbox` 폴더에서 발견된 항목 확인
4. 처리할 항목 선택
5. 자동 처리 시작
6. 처리 상태 확인
7. 후보가 생기면 Mapping으로 이동

사용자가 이 페이지에서 하지 않는 일:

- normalize/chunk/embed/extract/map을 개별 실행
- 후보 merge/create 결정
- wiki 문서 상세 탐색

## 2. PC 기본 화면 구조

```text
┌──────────────────────────────────────────────────────────────┐
│ Inbox                                                        │
│ 📥 처리할 자료를 추가하고 자동 처리를 시작합니다.                │
│ [Upload file] [Add text] [Scan folder]                        │
├──────────────────────────────────────────────────────────────┤
│ Left: Inbox source list        │ Right: Selected item detail  │
│ - filter/status tabs           │ - preview                    │
│ - compact rows                 │ - metadata/status chips       │
│ - multi-select                 │ - process CTA                 │
├──────────────────────────────────────────────────────────────┤
│ Bottom: Processing queue / recent results                     │
└──────────────────────────────────────────────────────────────┘
```

## 3. Tablet/Mobile 구조

Tablet:

- 2-column 유지 가능하면 유지
- 좁으면 list와 detail을 tab으로 전환

Mobile:

```text
Inbox header
Action buttons
Status filter chips
Source list
Tap item → detail sheet/page
Sticky CTA: Process selected
```

## 4. 상단 영역

### Header

- title: `Inbox`
- subtitle: `처리할 자료를 추가하고 자동 처리를 시작합니다.`
- status chips:
  - `New 4`
  - `Processing 2`
  - `Needs mapping 3`
  - `Failed 1`

### Primary actions

- `Upload file`
  - icon: upload
  - 설명: 파일을 추가합니다.
- `Add text`
  - icon: edit
  - 설명: 메모/텍스트를 바로 입력합니다.
- `Scan folder`
  - icon: folder-search
  - 설명: `00_Inbox` 폴더를 다시 확인합니다.

긴 설명은 상단에 두지 않는다.

## 5. 왼쪽 — Inbox source list

목적: 처리할 항목을 빠르게 훑고 선택한다.

### Filter tabs/chips

- `All`
- `New`
- `Processing`
- `Needs mapping`
- `Failed`
- `Completed`

### Row 정보

각 row는 카드가 아니라 compact list 형태.

```text
[ ] 📄 paper-rag.md               new             2m ago
    00_Inbox/files · markdown · 18 KB

[ ] ✏️ 직접 입력: agents memo       processing      now
    text input · raw saved ✓ extracting…
```

표시 필드:

- checkbox
- type icon
  - file
  - text
  - folder-detected
- title/file name
- origin
  - upload
  - text
  - `00_Inbox/memo`
  - `00_Inbox/files`
  - `00_Inbox/text`
- status chip
- updated/created time
- short progress line

### Status vocabulary

사용자에게 보이는 상태는 5개로 제한한다.

| Status | 의미 |
|---|---|
| `new` | 아직 처리하지 않음 |
| `processing` | 자동 처리 중. 진행 로그 확인 가능 |
| `needs_mapping` | 후보가 생겨 Mapping에서 결정 필요 |
| `completed` | 처리 결과가 확정/종료되어 기록을 살필 수 있음. 어떤 모델/스키마/프롬프트/결과/아티팩트가 사용·생성됐는지 확인하는 상태 |
| `failed` | 처리 실패, 재시도 가능 |

내부 상태 `ingested`, `normalized`, `chunked`, `embedded`, `extracted`, `mapped`는 기본 list status로 노출하지 않고 progress/detail에서만 짧게 표시한다.

## 6. 오른쪽 — Selected item detail

목적: 선택한 항목이 무엇인지 확인하고 처리한다.

### Detail header

- title/file name
- origin path
- status chip
- duplicate warning, if any

### Preview

- Markdown/text preview는 viewer 형태
- raw text가 길면 일부만 표시 + expand
- PDF/Office/URL 등 향후 지원 타입은 placeholder/error 안내

### Metadata

- source path
- detected type
- size
- modified time
- raw source path, if created
- generated candidate count, if available

### Process status

progress chip 예:

```text
raw saved ✓ · extracting… · mapping pending
```

실패 예:

```text
extract failed · retry available
```

### Processing log

`processing` 상태에서는 사용자가 진행 로그를 볼 수 있어야 한다.

표시 방식:

- 기본 list에는 짧은 progress chip만 표시
- detail panel에 `View processing log` 버튼 제공
- log는 단계별 short event timeline으로 표시
- raw CLI log 전문은 `technical details`에 접어둔다

예:

```text
12:30 source registered
12:30 raw saved
12:31 normalized
12:31 chunks created: 8
12:32 embedding completed
12:33 candidates extracted: 4
12:33 mapping candidates ready: 2
```

실패 시:

```text
12:31 extract failed
reason: model timeout
[Retry] [View technical log]
```

### Detail actions

- `Process this item`
- `Retry`
- `Open Mapping` when status is `needs_mapping`
- `View processing log` when status is `processing` or `failed`
- `View result record` when status is `completed`
- `View log` as secondary/details action

## 7. 하단 — Processing queue / recent results

목적: 자동 처리 중인 항목과 최근 결과를 작게 보여준다.

표시:

- currently processing count
- recent failed count
- recent needs_mapping count
- last scan time

예:

```text
Processing: 2 · Needs mapping: 3 · Failed: 1 · Last scan: 12:30
```

CTA:

- `Open Mapping`
- `Retry failed`

## 8. Upload file flow

1. `Upload file` 클릭
2. 파일 선택 modal 또는 OS picker
3. 선택 파일 목록 표시
4. `Add to Inbox`
5. list에 `new` 상태로 추가
6. 사용자가 `Process selected` 또는 `Process this item`

초기 허용 타입:

- Markdown/text 우선
- PDF/Office/HTML/URL은 Phase 2에서 지원된 범위만 허용하거나, unsupported 안내

## 9. Add text flow

1. `Add text` 클릭
2. modal 또는 side panel
3. title 입력
4. text 입력
5. `Add to Inbox`
6. list에 `new` 상태로 추가

필수 필드:

- title
- text

선택 필드:

- tags
- source note

## 10. Scan folder flow

1. `Scan folder` 클릭
2. `vault/00_Inbox/{memo,files,text}` 스캔
3. 신규/중복/이미 처리됨 count 표시
4. 새 항목을 list에 추가

스캔 결과 요약:

```text
3 new · 1 duplicate · 8 already processed
```

## 11. Process flow

사용자는 한 번만 누른다.

```text
Process selected
```

내부 자동 pipeline:

```text
ingest → raw save → normalize → chunk → embed → extract/link → map candidates
```

사용자에게는 다음 상태만 보인다.

```text
processing → needs_mapping / completed / failed
```

후보가 생성되면:

- 해당 row status: `needs_mapping`
- detail CTA: `Open Mapping`
- bottom queue: `Needs mapping +N`

처리 또는 mapping 결정이 종료되면:

- 해당 row status: `completed`
- detail에 결과 기록 표시
- 필요 시 `Open Wiki`, `Open Mapping record`, `View source` CTA 제공

## 12. Completed result record

`completed`는 단순히 목록에서 사라지는 상태가 아니라, 처리 결과를 되짚어보는 기록 뷰를 제공해야 한다.

표시해야 할 정보:

### Source summary

- source title/path
- origin: upload/text/00_Inbox
- processed time
- final state: no candidates / mapped / created / rejected / mixed

### Model/run summary

- task type
- provider
- model id/name
- prompt version
- schema version
- run status
- started/finished time
- latency, if available

### Result summary

- generated candidates count
- approved/merged count
- created concept count
- rejected/retry count
- linked wiki pages/concepts

### Artifacts

- LLM candidate JSON artifact
- validation result
- retry instruction, if any
- compile preview/diff, if any
- sync result, if applied

### Display policy

- 기본은 사람이 읽는 요약 중심
- schema JSON, raw LLM response, CLI logs는 접힘 영역
- 모델/API key 같은 민감 정보는 key 값 없이 provider/model/status만 표시

예:

```text
Model: ollama / llama3.1:8b
Prompt: extract_claims confirmed v3
Schema: candidate-envelope v1
Result: 4 candidates → 2 merged, 1 created, 1 rejected
Artifacts: candidate.json · validation.json · sync-dry-run.md
```

## 12-1. Error placement

Inbox 오류는 실패한 source item의 detail 안에서 해결한다.

표시 위치:

- 상단 status chips: `Failed N`
- 왼쪽 source list: 실패 item row에 `failed` chip
- 오른쪽 selected item detail:
  - error summary
  - suggested fix
  - `Retry`
  - `View processing log`
  - technical details 접힘
- 하단 processing queue: recent failed jobs 요약

다른 페이지로 이동이 필요한 경우:

- LLM 연결 문제 → `Settings LLM`
- 파일/경로 문제 → `Vault Browser` 또는 `Onboarding Vault`
- 후보 생성 완료 → `Mapping`

## 13. Empty/Error 상태

### Empty

```text
처리할 자료가 없습니다.
[Upload file] [Add text] [Scan folder]
```

### Upload unsupported

```text
이 파일 형식은 아직 지원하지 않습니다.
Markdown 또는 text 파일을 먼저 추가하세요.
```

### Processing failed

```text
자동 처리 중 실패했습니다.
[Retry] [View log]
```

### Duplicate detected

```text
이미 처리된 파일과 유사합니다.
[View existing source] [Process anyway]
```

## 14. 필요한 API 초안

```text
GET  /api/inbox/items
GET  /api/inbox/items/{item_id}
GET  /api/inbox/items/{item_id}/result-record
POST /api/inbox/upload
POST /api/inbox/text
POST /api/inbox/scan
POST /api/inbox/process
POST /api/inbox/items/{item_id}/retry
GET  /api/inbox/status
```

## 15. 승인 기준

- 사용자가 Inbox를 “자료를 넣고 자동 처리를 시작하는 곳”으로 이해한다.
- 중간 CLI 단계가 복잡하게 노출되지 않는다.
- PC에서 list/detail/queue 구조가 한눈에 보인다.
- 모바일에서는 list → detail → CTA 흐름이 깨지지 않는다.
- 후보 생성 후 Mapping으로 가야 함이 명확하다.
- 파일 업로드와 텍스트 입력이 모두 지원된다.
- completed 항목에서 모델/프롬프트/스키마/결과/아티팩트 기록을 확인할 수 있다.

## 16. 확인 필요

- 현재 없음. Inbox UX는 임시 확정 상태로 다음 Mapping 페이지 검토로 넘어갈 수 있다.
