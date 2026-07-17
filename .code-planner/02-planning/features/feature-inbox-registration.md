# Feature Contract — Inbox registration and movement

## 목적

세 입력 유형을 Inbox로 받고 처리 결과에 따라 올바른 폴더로 이동한다.

## 입력 유형과 권장 Inbox 하위 폴더

### 1. Document files

- PDF/DOCX/PPTX/HTML/TXT/MD 등 parser 지원 파일.
- Inbox에 들어온 뒤 parser로 텍스트 추출한다.
- 권장 위치: `Inbox/Files`.

### 2. Markdown/Obsidian scrape

- `.md`, `.markdown` 파일.
- frontmatter/title/url/tags가 있으면 source metadata로 보존한다.
- 내부 wikilink는 신뢰된 Wiki link가 아니라 source text로 취급한다.
- 권장 위치: `Inbox/Markdown`.

### 3. Pasted text

- Web UI/CLI 입력을 `.md` source-like 파일로 생성한다.
- 권장 위치: `Inbox/Text`.
- 최소 metadata:
  - title
  - input_type: pasted_text
  - created_at
  - optional source_url/tags
- pasted text의 tags/source_url은 생성되는 `.md` 파일 frontmatter에 저장한다.

### 4. Existing Raw Sources import

- 기존 vault/Raw Sources 문서는 정상 queue가 아니라 기존 자료 source material이다.
- 사용자가 `/ingest`에서 “Raw Sources에서 Inbox로 가져오기”를 선택하면 해당 문서를 Inbox pending item으로 등록한다.
- 처리 전에는 Raw Sources 파일이 직접 job queue에 들어가면 안 된다.

## 파일 이동 규칙

```text
Inbox incoming
→ processing DB state/lock
→ success: Raw Sources archive
→ failed: Inbox/_Failed
→ review: Inbox/_Review
```

`Inbox/_Processing` 실제 폴더는 만들지 않는다. 처리 중 상태는 DB state/lock으로 표현한다.

## 실패 로그

- `_Failed`에는 원본과 함께 diagnostic report를 남긴다.
- 포함 후보:
  - error type
  - phase
  - sanitized LLM/provider error
  - source path
  - trace/job id
  - retry hint
- 오류 확인/처리 후 report 삭제 가능.

## Acceptance criteria

- 업로드/붙여넣기/파일 추가가 모두 Inbox item을 생성한다.
- 성공 시 원본은 Raw archive로 이동한다.
- 실패 시 원본은 `_Failed`로 이동하고 로그가 남는다.
- review 시 원본/후보는 `_Review`로 이동한다.
- 처리 중 상태는 물리 폴더 이동이 아니라 DB 상태로 추적된다.
- 기존 Raw Sources import도 Inbox pending item을 생성한 뒤 처리된다.
