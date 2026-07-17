# Mockup Spec — Inbox-first Ingest Screen (existing UX based)

## 목적

기존 `/ingest` 화면의 drop zone, pending queue, recent jobs 구조를 유지하면서 Raw-first 문구와 동작을 Inbox-first로 바꾼다.

## 주요 사용자 흐름

1. 사용자가 `/ingest`에 들어온다.
2. Files/Markdown/Text 입력 중 하나를 선택한다.
3. 항목이 Inbox pending으로 등록된다.
4. 기존 Raw Sources 문서를 사용할 때는 “Raw Sources에서 Inbox로 가져오기”를 눌러 pending Inbox item으로 만든다.
5. 사용자가 선택 항목 또는 전체 Inbox pending을 처리 시작한다.
6. Jobs 영역에서 processing/chunk extraction/review/failed 상태를 본다.

## Screen: Ingest

```text
┌─────────────────────────────────────────────────────────────┐
│ 수집                                                        │
│ 새 입력을 Inbox에 등록하고 처리 대기열로 보냅니다.          │
├─────────────────────────────────────────────────────────────┤
│ [파일 업로드 Drop Zone]                                      │
│ PDF · DOCX · PPTX · Markdown · HTML · TXT                   │
├─────────────────────────────────────────────────────────────┤
│ [붙여넣기 텍스트] title / url / body / tags / [Inbox 저장]   │
│ [Raw Sources에서 Inbox로 가져오기] 기존 자료 import           │
├─────────────────────────────────────────────────────────────┤
│ Inbox 대기열                                                 │
│ [ ] item.md  document_file  pending                         │
│ [ ] paste-title.md pasted_text pending                       │
│ [선택 처리 시작] [전체 처리]                                │
├─────────────────────────────────────────────────────────────┤
│ 최근 작업                                                    │
│ #12 processing chunk extraction  40%                         │
│ #11 failed parser error [원인 보기]                           │
└─────────────────────────────────────────────────────────────┘
```

## Empty state

- “Inbox 대기 항목이 없습니다.”
- Raw Sources CTA는 “처리 대기열 스캔”이 아니라 “기존 자료를 Inbox로 가져오기”로만 표시한다.

## Success state

- 입력 등록 성공: Inbox queue에 item 표시.
- ingest 성공: Raw archive path와 생성/업데이트 page count 표시.

## Failure state

- parser/LLM/lint 실패: `_Failed`로 이동됨을 표시하고 원인 보기 링크 제공.
- review 필요: `_Review`로 이동됨을 표시하고 Review 열기 링크 제공.

## Review questions

- Files/Markdown/Text를 같은 화면에 둘지, Text는 접이식 panel로 둘지?
- 기존 Raw Sources 기능은 import/migration으로만 남기는 것이 적절한가?
- Jobs 카드에서 chunk progress를 어느 정도까지 보여줄지?

## 결정

- chunk extraction progress 표시는 Build scope에 포함한다.
- 표시 수준은 job phase label과 percentage 수준으로 제한한다.
- chunk별 원문 내용은 job card에 노출하지 않는다.
- 입력 하위 폴더 convention은 `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`로 한다.
- `Inbox/Articles` 같은 세부 분류는 폴더 사양이 아니라 category/metadata로 다룬다.
- HTML artifact는 PRV-confirmed이며, queue 예시는 권장 convention에 맞춰 `Inbox/Files`/`Inbox/Text`를 사용한다.
- 2026-07-16 보정: Raw Sources는 archive이며, 기존 자료는 Inbox로 가져온 뒤 처리한다. UX 테스트는 Inbox-to-Job mapping이 통과된 뒤 수행한다.
- HTML mockup의 `imported` badge는 pending 계열 상태로 표시한다. 구현 시 별도 색을 추가하거나 `pending` 스타일을 재사용해도 된다.
- `pasted_text`, `document_file`, `imported` 등은 상태가 아니라 input_type/등록 출처 라벨이다. 구현 시 status badge(`pending`, `processing`, `failed`)와 분리하거나 pending 계열 보조 pill로 표시한다.

## HTML/Lavish note

사용자는 별도 신규 목업 구현을 원하지 않았다. 따라서 Planning 후반 review에서는 기존 `/ingest` UX 기반 최소 HTML artifact만 만들고, 새 디자인이 아니라 기존 화면 확장 검토로 제한한다.
