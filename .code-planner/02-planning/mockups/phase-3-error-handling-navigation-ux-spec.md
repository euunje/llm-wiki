# Phase 3 UX Spec — Error Handling and Navigation

## Review status

- Status: `drafted_review_pending`
- Scope: 오류/실패 상태가 어느 메뉴와 화면에 연결되는지 정의

## 1. 기본 원칙

오류 처리는 독립 최상위 메뉴로 만들지 않는다.

대신 다음 두 경로로 연결한다.

```text
1. Dashboard → Issues / Errors summary
2. 각 기능 페이지 → 해당 항목의 contextual error 상태
```

이유:

- 오류는 원인이 발생한 작업/페이지 맥락에서 해결해야 한다.
- 별도 Error 메뉴는 사용자가 “어디로 돌아가 고쳐야 하는지”를 다시 판단하게 만든다.
- Dashboard는 전체 상태를 모아 보여주는 진입점 역할을 한다.

## 2. 메뉴 연결 구조

권장 top navigation:

```text
Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings
```

Logout은 top-level nav에 두지 않는다. 향후 사용자 메뉴 dropdown에 배치하며, 사용자 메뉴가 아직 없으면 Settings > Auth의 임시 액션으로만 제공한다.

모바일에서는 위 top navigation을 상단에 나열하지 않는다. 좌측 사이드 메뉴 버튼(☰)으로 drawer를 열고, drawer 안에서 `Onboarding / Dashboard / Inbox / Mapping / Vault / Wiki / Settings` 및 Mapping/Settings 세부 메뉴에 진입한다.

오류는 별도 top nav가 아니라 아래처럼 연결한다.

```text
Dashboard
  └─ Issues / Errors card
       ├─ Inbox failed item → Inbox detail
       ├─ Mapping decision failed → Mapping candidate
       ├─ LLM connection failed → Settings LLM
       ├─ Vault path/read failed → Vault Browser or Onboarding Vault
       ├─ Wiki render failed → Wiki document
       └─ Prompt/schema failed → Settings Prompt
```

## 3. Dashboard에서 보여줄 오류 요약

Dashboard에는 `Issues` 또는 `Needs attention` 영역을 둔다.

표시 예:

```text
Needs attention

📥 Inbox failed      2   [Open]
🧭 Mapping pending   3   [Open]
🔌 LLM error         1   [Fix]
📁 Vault read error  1   [Open]
```

각 row는 원인 화면으로 이동한다.

## 4. 페이지별 오류 연결

### Inbox

오류 예:

- upload 실패
- unsupported file
- scan 실패
- processing 실패
- LLM 처리 timeout

표시 위치:

- Inbox source row status: `failed`
- selected item detail
- processing log

CTA:

- `Retry`
- `View processing log`
- `Edit input`
- `Open Settings LLM` if model/connection issue

Inbox 안에서의 권장 위치:

```text
Inbox
├─ 상단 status chips
│  └─ Failed N 표시
├─ 왼쪽 source list
│  └─ 실패한 item row에 failed chip 표시
├─ 오른쪽 selected item detail
│  ├─ error summary
│  ├─ suggested fix
│  ├─ Retry / View processing log
│  └─ technical details 접힘
└─ 하단 processing queue
   └─ recent failed jobs 요약
```

즉, Inbox 오류는 별도 페이지가 아니라 **실패한 source item의 detail 안**에서 해결한다.

### Mapping

오류 예:

- 후보 detail load 실패
- wiki match 계산 실패
- decision 저장 실패
- relationship validation 실패

표시 위치:

- 후보 queue row
- 현재 wizard step 상단
- decision confirmation 실패 상태

CTA:

- `Retry`
- `Edit`
- `Reject + retry instruction`
- `View technical details`

Mapping 안에서의 권장 위치:

```text
Mapping [new: N]
├─ 왼쪽 candidate queue
│  └─ 실패/문제 후보 row에 warning chip 표시
├─ 중앙 3-step wizard
│  ├─ Step 1 Page 검증 오류: page 후보 내용 위쪽
│  ├─ Step 2 Page Mapping 오류: 유사 wiki 비교 영역 위쪽
│  └─ Step 3 Relationship 오류: relation graph/list 위쪽
├─ ④ 오류/에러 탭
│  └─ retry with instruction / rejected / technical details
└─ 하단 action bar
   └─ decision 저장 실패 시 inline error + Retry
```

즉, Mapping 오류는 **현재 후보의 현재 step에서 감지하고, ④ 오류/에러 탭에서 재시도/거절을 처리한다.**

오류 종류별 위치:

| 오류 | 표시 위치 | 주 CTA |
|---|---|---|
| 후보 JSON/schema 오류 | Step 1 Page 검증 | Reject + retry instruction |
| 후보 본문/제목 오류 | Step 1 Page 검증 | Edit / Reject |
| 기존 wiki 유사 항목 load 실패 | Step 2 Page Mapping | Retry search |
| merge target 불명확 | Step 2 Page Mapping | Select target / Edit |
| relation direction/label 오류 | Step 3 Relationship 검증 | Edit relation |
| decision 저장 실패 | action bar | Retry save |
| LLM 재평가 필요 | ④ 오류/에러 | Retry with instruction |

### Settings LLM / Models / Routes

오류 예:

- provider endpoint unreachable
- API key missing/invalid
- model list empty
- embedding model download 실패
- route capability mismatch
- concurrent tasks timeout 증가

표시 위치:

- Connection status
- Model registry row
- Advanced options route row

CTA:

- `Test connection`
- `Refresh models`
- `Load fastembed models`
- `Use this model` disabled reason
- `Lower concurrency to 1`

### Vault Browser / Onboarding Vault

오류 예:

- path not found
- permission denied
- folder mapping incomplete
- file read failed

표시 위치:

- Vault Browser folder/file viewer
- Onboarding Vault setup step

CTA:

- `Choose another path`
- `Open Onboarding Vault setup`
- `Retry read`

### Wiki

오류 예:

- document not found
- markdown render failed
- graph load failed
- relation target missing

표시 위치:

- document reader
- graph section at bottom

CTA:

- `Back to Wiki list`
- `Show raw markdown`
- `Open Mapping`

### Settings Prompt

오류 예:

- prompt schema mismatch
- test prompt failed
- confirmation failed

표시 위치:

- prompt version row
- prompt editor/test result

CTA:

- `Edit prompt`
- `Run test`
- `View schema error`

## 5. Error record detail

각 오류는 가능한 경우 공통 detail 구조를 가진다.

```text
Error summary
Where it happened
Suggested fix
Retry action
Technical details
```

Technical details 기본 숨김:

- stack trace
- raw API response
- raw LLM response
- CLI command/log

## 6. Completed/failed 기록과 연결

- Inbox `failed`: 실패 항목 detail에서 processing log 확인
- Inbox `completed`: model/prompt/schema/result/artifact 기록 확인
- Dashboard Issues: failed/pending만 모아 빠른 진입 제공

## 7. 승인 기준

- 사용자가 Dashboard에서 전체 오류 수와 위치를 알 수 있다.
- 오류 row를 누르면 원인 페이지의 해당 항목으로 이동한다.
- 각 페이지는 자기 맥락에서 오류 해결 CTA를 제공한다.
- 기술 로그는 기본 숨김이다.
- 별도 Error 최상위 메뉴 없이도 오류 탐색이 가능하다.
