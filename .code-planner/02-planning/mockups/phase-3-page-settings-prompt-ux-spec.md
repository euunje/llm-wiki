# Phase 3 Page UX Spec — Settings: Prompt

## Review status

- Status: `drafted_review_pending`
- Scope: Prompt settings/version/history/rollback UX
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- Rollback은 기존 archived row를 직접 confirmed로 바꾸지 않는다.
- Rollback 시 선택 version의 복사본을 새 confirmed version으로 만든다.
- 원본 version history는 보존한다.
- 테스트 실패 prompt의 `Confirm anyway`는 1차 UX에서 제외한다.

## 확인된 현재 구현/Phase 2 기반

Phase 2 기본 프롬프트는 실제 코드에 존재한다.

- Source: `src/llm_wiki/schema/prompts.py`
- 기본 prompt dict: `DEFAULT_PROMPTS`
- 기본 version label: `phase2-default-v1`
- 기본 state: `confirmed`
- bootstrap 시:
  - DB `prompt_versions`에 confirmed prompt seed
  - `vault/90_Settings/prompts/{task_type}.md` 파일 생성

현재 기본 task:

```text
extract_claims
map
link
summarize
compile
ask
```

따라서 Settings Prompt 화면은 “Phase 2 기본 프롬프트가 반영됐는지”를 명확히 보여줘야 한다.

## 문제

현재 Prompt 화면에서 부족한 점:

- 현재 적용 중인 prompt가 무엇인지 불명확함
- Phase 2 default prompt가 반영됐는지 불명확함
- confirmed/test/archived 구분이 약함
- version history가 아래에 명확히 없음
- rollback 기능이 없음
- prompt test 결과와 confirm 흐름이 충분히 보이지 않음

## 1. 페이지 목적

Settings Prompt는 작업별 prompt를 확인하고, test version을 만들고, 테스트 후 confirmed로 승격하거나 이전 version으로 rollback하는 화면이다.

사용자가 이 페이지에서 하는 일:

1. task별 현재 적용 prompt 확인
2. Phase 2 default prompt 반영 여부 확인
3. test prompt 작성/저장
4. prompt test 실행 결과 확인
5. test version을 confirmed로 승격
6. version history 확인
7. 이전 confirmed/archived version으로 rollback

## 2. PC 기본 화면 구조

```text
┌──────────────────────────────────────────────────────────────┐
│ Settings > Prompt                                            │
├───────────────┬──────────────────────────────────────────────┤
│ Task list     │ Prompt workspace                             │
│ - extract     │ 1. Active prompt status                      │
│ - map         │ 2. Prompt editor / test version              │
│ - link        │ 3. Test result                               │
│ - summarize   │ 4. Version history + rollback                │
└───────────────┴──────────────────────────────────────────────┘
```

## 3. Task list

목적: 어떤 작업의 prompt를 보고 있는지 명확히 한다.

표시:

- task label
- internal task id
- active state chip
- default source chip

예:

```text
Extract claims     confirmed · phase2-default-v1
Map candidates     confirmed · phase2-default-v1
Link relations     confirmed · phase2-default-v1
Summarize          confirmed · phase2-default-v1
Compile wiki       confirmed · phase2-default-v1
Ask                confirmed · phase2-default-v1
```

만약 사용자가 수정한 confirmed prompt라면:

```text
Map candidates     confirmed · custom-v3
```

## 4. Active prompt status

목적: 현재 실제로 사용되는 prompt를 명확히 보여준다.

표시:

- task type
- active prompt id
- version label
- state: confirmed
- source:
  - Phase 2 default
  - user confirmed
  - rollback restored
- created/confirmed time
- change note
- schema compatibility

예:

```text
현재 적용 중
Task: map
Version: phase2-default-v1
Source: Phase 2 default prompt
State: confirmed
Schema: candidate.v1 compatible
```

## 5. Prompt editor / test version

목적: 현재 confirmed prompt를 기반으로 test version을 만든다.

표시:

- base confirmed prompt
- editable test prompt textarea
- change note 필수
- 저장 후 state: test

Actions:

- `Save test version`
- `Run prompt test`
- `Discard draft`

정책:

- editor는 기본적으로 active confirmed prompt를 복사해서 시작
- 저장 전에는 실제 작업에 반영되지 않음
- test version은 confirmed 되기 전까지 production task에 사용되지 않음

## 6. Test result

목적: test prompt가 schema와 원하는 출력에 맞는지 확인한다.

표시:

- test run status
- used model
- prompt version id
- schema validation result
- sample input
- generated candidate count
- error summary
- artifact links

Actions:

- `Run test`
- `View artifacts`
- `Confirm this version`, only if test passed or user explicitly allows

## 7. Version history + rollback

목적: 아래 영역에서 전체 version history를 보고 이전 version으로 되돌릴 수 있게 한다.

위치:

- Prompt workspace 하단 고정 section

표시:

```text
Version history

confirmed  custom-v3          2026-07-19  현재 적용 중
archived   phase2-default-v1   2026-07-10  Phase 2 default prompt
test       web-test-v4         2026-07-19  테스트 중
archived   custom-v2           2026-07-18
```

각 row 표시:

- state: confirmed / test / archived
- version label
- source: Phase 2 default / user / rollback
- created time
- confirmed time
- change note
- schema compatibility chip
- actions

Actions:

- confirmed current: `Current`
- test: `Confirm`, `Delete/Discard` optional
- archived: `Rollback to this version`
- any: `View diff`, `View full prompt`

## 8. Rollback flow

Rollback은 archived/previous version의 복사본을 새 confirmed version으로 생성하는 기능이다.

Flow:

1. version history에서 `Rollback to this version`
2. confirmation modal
3. 현재 confirmed는 archived 처리
4. 선택 version의 복사본을 새 confirmed version으로 생성
5. change note에 rollback 기록

Confirmation 예:

```text
phase2-default-v1로 rollback합니다.
현재 confirmed custom-v3는 archived 됩니다.

Reason
[ custom prompt가 mapping schema를 깨뜨려 기본 prompt로 복구 ]

[Confirm rollback] [Cancel]
```

정책:

- rollback도 change history에 남긴다.
- rollback 후 active prompt status가 즉시 갱신된다.
- rollback된 version source는 `rollback restored`로 표시한다.
- 원본 archived/test row는 수정하지 않고 history로 보존한다.

## 9. Phase 2 default prompt 표시 정책

Phase 2 default prompt는 빈약하게 보이면 안 된다. UI에서 다음을 보여준다.

- 이 prompt가 Phase 2에서 seed된 기본 prompt인지
- language policy가 포함되어 있는지
- candidate schema 정책이 포함되어 있는지
- task별 역할이 무엇인지

예:

```text
Phase 2 default prompt
✓ candidate.v1 JSON only
✓ Korean explanation + preserve English technical terms
✓ no human_decision/retry_instruction output
✓ evidence required
```

## 10. Empty/Error 상태

### No prompt found

```text
이 task의 prompt가 없습니다.
[Restore Phase 2 default]
```

### Test failed

```text
Prompt test failed.
Schema validation error: mapping_action is missing.
[Edit prompt] [View artifacts]
```

### Confirm blocked

```text
테스트를 통과하지 않은 prompt입니다.
[Run test]
```

정책: 테스트 실패 prompt의 `Confirm anyway`는 1차 UX에서 제공하지 않는다.

### Rollback failed

```text
Rollback에 실패했습니다.
[Retry] [View technical details]
```

## 11. 필요한 API 초안

현재 일부 API는 존재한다.

Existing:

```text
GET  /api/settings/prompt-versions
POST /api/settings/prompt-versions
POST /api/settings/prompt-versions/{prompt_id}/confirm
GET  /api/settings/prompts/history?task_type=...
```

Needed/clarify:

```text
GET  /api/settings/prompts/active?task_type=...
POST /api/settings/prompts/{prompt_id}/test
POST /api/settings/prompts/{prompt_id}/rollback
GET  /api/settings/prompts/{prompt_id}/diff?against=...
POST /api/settings/prompts/restore-default
```

## 12. 승인 기준

- 현재 적용 중인 prompt가 무엇인지 보인다.
- Phase 2 default prompt가 반영됐는지 보인다.
- confirmed/test/archived 상태가 명확하다.
- 아래에 version history가 있다.
- archived version으로 rollback할 수 있다.
- test version은 confirm 전까지 실제 작업에 반영되지 않는다.
- prompt test 결과와 schema validation 결과가 보인다.
- prompt 오류는 Settings Prompt 안에서 수정/rollback/test로 해결할 수 있다.

## 13. 확인 필요

- 현재 없음. Settings Prompt UX는 임시 확정 상태로 다음 페이지 검토로 넘어갈 수 있다.
