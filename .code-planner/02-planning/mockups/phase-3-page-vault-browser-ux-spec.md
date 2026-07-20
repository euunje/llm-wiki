# Phase 3 Page UX Spec — Vault Browser

## Review status

- Status: `drafted_review_pending`
- Scope: Vault folder/file viewer UX
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- Vault Browser의 목적은 vault의 리스트와 내용을 파악하는 것이다.
- 기본적으로 읽기 전용이다.
- Markdown 파일은 Markdown viewer로 보여준다.
- 수정 기능은 현재 반영하지 않는다.
- 새 페이지 생성 기능은 현재 반영하지 않는다.

## 1. 페이지 목적

Vault Browser는 사용자가 전체 vault 폴더 구조와 파일 내용을 파악하는 화면이다.

사용자가 이 페이지에서 하는 일:

1. vault 폴더 구조 확인
2. 폴더별 파일 목록 확인
3. 파일 내용 읽기
4. Markdown 파일을 viewer로 보기
5. 현재 파일 위치 확인

사용자가 이 페이지에서 하지 않는 일:

- 파일 수정
- 새 wiki page 생성
- 파일 삭제/이동
- Mapping 결정
- Inbox 처리 시작

## 2. PC 기본 화면 구조

```text
┌──────────────────────────────────────────────────────────────┐
│ Vault Browser                                                │
│ 📁 Vault 폴더와 파일 내용을 읽기 전용으로 확인합니다.           │
├──────────────────────────────────────────────────────────────┤
│ Left: Folder tree       │ Middle: File list                   │
│ - 00_Inbox              │ - selected folder files             │
│ - 10_Wiki               │ - type/status icons                 │
│ - 20_Review             │ - search/filter                     │
│ - 80_Raws               │                                    │
│ - 90_Settings           │ Right: File viewer                  │
│                         │ - file path                         │
│                         │ - markdown viewer / text preview     │
└──────────────────────────────────────────────────────────────┘
```

PC에서는 3-column 구조를 기본으로 한다.

1. Folder tree
2. File list
3. File viewer

## 3. Tablet/Mobile 구조

Tablet:

- folder tree + file list를 왼쪽 panel로 묶고 viewer를 크게 표시
- 또는 `Folders / Files / Viewer` tab 전환

Mobile:

```text
Vault Browser
[Folders] [Files] [Viewer]

Step 1: folder 선택
Step 2: file 선택
Step 3: viewer에서 크게 읽기
```

모바일에서는 파일 내용을 크게 읽는 것이 우선이다.

## 4. Folder tree

목적: vault 구조를 빠르게 파악한다.

표시 기본 루트:

```text
vault/
  00_Inbox/
    memo/
    files/
    text/
  10_Wiki/
    concepts/
    sources/
    claims/
    pages/
  20_Review/
    candidates/
    mapping/
    rejected/
  80_Raws/
  90_Settings/
    templates/
    prompts/
    ontology/
```

표시:

- folder icon
- folder name
- file count, optional
- selected folder highlight

숨김:

- 숨김 폴더 기본 숨김
- 권한 없는 폴더 숨김 또는 disabled 표시 중 구현에서 안전한 방식 선택

## 5. File list

목적: 선택한 폴더 안의 파일을 확인한다.

표시:

- file name
- file type icon
- extension
- size
- modified time
- optional status hint

형태:

```text
📄 rag.md                 md      12 KB   2026-07-19
📄 vector-search.md       md       8 KB   2026-07-18
🧾 sync-status.md         md       2 KB   2026-07-18
```

검색/필터:

- file name search
- extension filter
- modified recently

## 6. File viewer

목적: 파일 내용을 읽는다.

상단:

```text
rag.md
vault/10_Wiki/concepts/rag.md
[Copy path] [Open in Wiki] optional
```

Viewer:

- `.md`: Markdown viewer로 렌더링
- `.txt`: text preview
- `.json`: pretty JSON viewer 또는 collapsed text
- 기타: unsupported preview 안내

Markdown policy:

- frontmatter는 본문에 직접 노출하지 않음
- frontmatter는 `Metadata` details에 표시 가능
- raw markdown은 `Raw` details/toggle에서만 표시

읽기 전용 정책:

- `Edit` 버튼 없음
- `New page` 버튼 없음
- `Delete`, `Move`, `Rename` 없음

## 7. Wiki 페이지와의 차이

Vault Browser:

- vault 파일 구조를 탐색하는 곳
- 모든 vault 영역을 볼 수 있음
- 읽기 전용

Wiki:

- 확정된 wiki 문서를 읽고 관계를 탐색하는 곳
- wiki 문서 중심
- graph/relation 탐색 제공

## 8. Empty/Error 상태

### No folder selected

```text
왼쪽에서 폴더를 선택하세요.
```

### Empty folder

```text
이 폴더에는 파일이 없습니다.
```

### File preview unsupported

```text
이 파일 형식은 미리보기를 지원하지 않습니다.
[Download/Open path]는 구현 범위에 따라 optional
```

### File read failed

```text
파일을 읽을 수 없습니다.
권한 또는 경로를 확인하세요.
```

## 9. 필요한 API 초안

```text
GET /api/vault/tree
GET /api/vault/folder?path=...
GET /api/vault/file?path=...
GET /api/vault/search?q=...
```

주의:

- 전체 경로 접근 정책은 Onboarding file browser와 일관되어야 한다.
- path traversal 방지 필요.
- source-controlled 외부 파일 쓰기 없음.

## 10. 승인 기준

- 사용자가 vault 폴더 구조를 파악할 수 있다.
- 사용자가 선택한 폴더의 파일 목록을 볼 수 있다.
- Markdown 파일은 viewer로 읽힌다.
- frontmatter는 본문 상단에 보이지 않는다.
- 수정/새 페이지 생성/삭제/이동 기능이 보이지 않는다.
- PC에서 folder tree / file list / viewer가 한 화면에 보인다.
- 모바일에서 folder → file → viewer 흐름이 자연스럽다.

## 11. 확인 필요

- 현재 없음. Vault Browser는 읽기 전용 viewer로 임시 확정 가능하다.
