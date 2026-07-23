# LLM Wiki Local

현재 기준은 Phase 3 normal-operation 웹 계약입니다. 구계약/하위호환 기대는 폐기되었습니다.

## 현재 웹 계약 요약

- `setup_complete`는 설정값 존재만으로 켜지지 않습니다. **실제 LLM 연결 테스트(chat + embedding) 통과**가 필요합니다.
- setup이 끝나기 전까지 Onboarding이 게이트입니다. 보호 페이지는 미완료 시 `/onboarding`으로 리다이렉트됩니다.
- Onboarding vault 폴더 브라우저는 **workspace root가 아니라 실제 HOME(`Path.home()`)에서 시작**합니다. 따라서 `~/vault` 같은 폴더를 직접 선택할 수 있습니다.
- Onboarding 폴더 브라우저는 **HOME 밖으로 올라갈 수 없고**, `..` 경로 이동, HOME 밖 절대경로, 숨김(`.`) 경로, symlink 경로를 거부합니다. 목록에서도 symlink는 숨깁니다.
- 기존 vault 매핑은 `~/vault` 또는 HOME 하위의 안전한 절대경로를 받아 저장할 수 있지만, **runtime/data/db/cache/artifacts 경로를 사람용 vault 아래로 강제로 옮기지 않습니다**. 현재 workspace runtime 경로는 그대로 유지됩니다.
- `30. Queries`는 **자동 raw query history dump가 아니라**, Search/Ask 결과에서 사용자가 명시적으로 **Save to Queries**를 눌렀을 때만 저장되는 사람용 질의/답변 보관함입니다. 기본 경로는 `role_map.queries` 또는 `<human_vault>/30. Queries` 입니다.
- Prompt Confirm는 **최신 passed `prompt_test_result` artifact**가 있어야 하며, 사용자 입력 label/note로 우회할 수 없습니다.
- Mapping Apply는 **preview-bound confirm**입니다. `preview_decision_id` 없이 직접 apply 하면 거부됩니다.
- Inbox processing은 현재 **동기(synchronous)** 처리이며, 응답의 현재 계약 필드는 `execution_mode`와 `acceptance_status`입니다.
  - `failed` / `blocked` / `degraded` 상태를 숨기지 않고 그대로 보고합니다.
  - `queued_count`가 남아 있더라도 이는 legacy/deprecated 호환 필드입니다.
- Logout은 기본 top navigation 항목이 아닙니다. 승인 UX 기준으로 `Settings > Auth`의 임시 액션에 위치합니다.

## 지원 문서 범위

현재 CLI/InBox ingest는 MarkItDown을 rich document 변환 백본으로 사용합니다. 지원 파일은 Markdown/text로 변환되어 `data/raw/*.md`에 저장된 뒤 기존 normalize/chunk/embed/wiki pipeline을 통과합니다.

| 범주 | 확장자 | 처리 방식 | 비고 |
|---|---|---|---|
| Markdown | `.md`, `.markdown` | 원문 ingest | 제목은 frontmatter `title` 또는 첫 `#` heading 기준 |
| Plain text | `.txt` | text parser → Markdown | 첫 non-empty line을 제목 후보로 사용 |
| Web document | `.html`, `.htm` | MarkItDown → Markdown | 기존 HTML parser는 fallback |
| PDF | `.pdf` | MarkItDown → Markdown | 텍스트 기반 PDF가 가장 안정적. 스캔 이미지 PDF는 OCR 설정/품질에 따라 실패/빈 결과 가능 |
| Word | `.docx` | MarkItDown → Markdown | 구형 `.doc`는 미지원 |
| PowerPoint | `.pptx` | MarkItDown → Markdown | 구형 `.ppt`는 미지원 |
| Excel | `.xlsx`, `.xls` | MarkItDown → Markdown | 표/시트 텍스트 중심 변환 |

현재 미지원/제한:

- `.doc`, `.ppt`: 구형 Office 바이너리 포맷입니다. 지원하려면 LibreOffice headless 변환 layer가 필요합니다.
- `.ppt`, `.doc`를 처리하려면 권장 경로는 `LibreOffice 변환 → .pptx/.docx → MarkItDown → Markdown`입니다.
- 이미지-only PDF, 스캔 문서, 이미지-heavy PPTX는 텍스트/OCR 품질에 따라 결과가 제한될 수 있습니다.
- URL ingest는 아직 기본 CLI ingest 대상이 아닙니다.

## Inbox 파일 저장 위치

현재 CLI `wiki inbox scan`과 Web Inbox scan/upload는 workspace root의 `./settings.yaml`을 읽고, Ja vault의 단일 Inbox queue를 사용합니다.

| 용도 | 저장 위치 | 현재 처리 상태 |
|---|---|---|
| 처리 대기 queue | `~/vault/00. Inbox` 바로 아래 파일 | `.md`, `.markdown`, `.txt`, `.html`, `.htm`, `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls` ingest 대상 |
| 처리/검토용 Markdown | `~/vault/00. Inbox/_Review` | 성공한 source의 Markdown preview가 `<실제파일명>_YYYYMMDD.md`로 생성됨. CLI scan 대상 아님 |
| 실패/보류용 | `~/vault/00. Inbox/_Failed` | 미지원/변환 실패 원본과 `<실제파일명>_YYYYMMDD.error.md` 리포트가 이동됨. CLI scan 대상 아님 |
| 원본 archive | `./data/inbox_originals` | 성공한 원본 파일이 vault 밖으로 이동됨 |
| pipeline raw | `./data/raw/*.md` | DB/pipeline source of truth |

주의:

- `Files`, `Text`, `Markdown`, `Memo` 같은 타입별 하위 폴더는 CLI Inbox 정책에서 제거되었습니다. 폴더가 있어도 기본 scan 대상이 아닙니다.
- CLI/Web scan은 `~/vault/00. Inbox` 바로 아래 파일만 처리하고 하위 폴더는 재귀 scan하지 않습니다.
- Web upload는 업로드 파일을 `~/vault/00. Inbox/<원본파일명>`으로 저장해 queue에 올립니다. 이름 충돌 시 `<원본파일명-stem>-2<suffix>`처럼 suffix를 붙입니다. 실제 ingest/archive/_Review 처리는 이후 Web/CLI Inbox scan에서 동일하게 수행됩니다.
- 성공 시 원본은 `./data/inbox_originals/`로 이동되어 Obsidian vault에서 제외됩니다.
- 성공 시 Markdown preview는 `~/vault/00. Inbox/_Review/<실제파일명>_YYYYMMDD.md`에 생성됩니다.
- PDF는 텍스트 기반 PDF가 가장 안정적입니다. 스캔 이미지 PDF처럼 텍스트가 추출되지 않는 파일은 OCR 설정/품질에 따라 `_Failed`로 이동될 수 있습니다.
- 구형 Word `.doc`, PowerPoint `.ppt`는 아직 기본 CLI Inbox ingest 대상이 아니며 `_Failed`로 이동됩니다.

현재 기본 설정 예:

```yaml
inbox:
  path: ~/vault/00. Inbox
  review_path: ~/vault/00. Inbox/_Review
  failed_path: ~/vault/00. Inbox/_Failed
```

## Environment-backed LLM defaults

- `.env.sample` documents the reusable keys: `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, and `LLM_WIKI_API_KEY`.
- Runtime settings are read from workspace-root `./settings.yaml`, not from the human vault.
- Chat LLM endpoint/model values may be resolved from the environment when `./settings.yaml` leaves them blank.
- Embedding model root/default model are read from `./settings.yaml` and local model cache/folders; they are not resolved from provider endpoint model lists.

## Saved Queries frontmatter

- 저장 타입은 `type: query_answer`, `status: saved`를 사용합니다.
- 기본 필드: `date`, `created_at`, `query`, `scope`, `source`, `relatedWiki`, `evidence`, `tags`, `generation`.
- `evidence` 항목은 가능한 범위에서 `title/path/url/target_type/target_id`를 기록하며, 로컬 vault markdown 경로는 본문에서 Obsidian wikilink로 표시합니다.

## CLI command surface

현재 CLI는 사용자/운영 명령과 debug/dev 명령을 분리합니다.

### 사용자/운영 명령

| Command | Purpose |
|---|---|
| `wiki init` | workspace 폴더, 설정, DB 초기화 |
| `wiki ingest <file.md> [--llm]` | Markdown ingest, normalize/chunk/embed, wiki page 생성, 선택적으로 LLM 후보 추출 |
| `wiki ingest-text <title> --text "..."` | raw text를 source로 등록 |
| `wiki inbox scan` | Inbox 폴더의 Markdown source 스캔 |
| `wiki ask "query"` | workspace 검색/RAG 질의 |
| `wiki search "query"` | FTS/metadata 검색 |
| `wiki status` | source/chunk/job/review 요약 |
| `wiki web` | FastAPI Web UI 실행 |
| `wiki settings get/set` | workspace 설정 조회/변경 |
| `wiki models list/test` | LLM 모델 목록/연결 테스트 |
| `wiki route get/set` | task → model route 조회/변경 |
| `wiki doctor` | 경로, DB, FTS, sqlite-vec, env, 모델 설정 점검 |
| `wiki healthcheck` | lint + status 기반 상태 점검 |

### Debug/dev 명령

| Command | Purpose |
|---|---|
| `wiki normalize <source_id>` | normalize 단계만 실행 |
| `wiki chunk <source_id>` | chunk 단계만 실행 |
| `wiki embed <target>` | embedding 단계만 실행 (`source:<id>`, `chunk:<id>`, `all`) |
| `wiki extract-claims <source_id> [--llm]` | claim/node 후보 추출 단계만 실행 |
| `wiki validate [target]` | candidate artifact/workspace 검증 report |
| `wiki lint [target]` | missing normalize/embed/failed jobs 등 lint report |
| `wiki debug-repair-source-stubs [--apply]` | 누락된 source stub markdown만 복구하는 debug용 repair |

### Removed/renamed commands

| Old command | Current status |
|---|---|
| `wiki fix` | 제거. 명확한 debug 명령 `wiki debug-repair-source-stubs`로 축소 |
| `wiki sync` | 제거 |
| `wiki retry` | CLI에서 제거. retry는 Web review/API 흐름에서 처리 |

## Run from source

```bash
PYTHONPATH=src python3 -m llm_wiki.cli --help
```
