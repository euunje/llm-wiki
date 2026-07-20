# Dependencies — LLM Wiki Local

## 확정/우선 후보

| 영역 | 후보 | 상태 | 메모 |
|---|---|---|---|
| Language | Python | accepted | CLI, LLM, SQLite 생태계 우선 |
| DB | SQLite | accepted | 상태/metadata/job/artifact/search 저장 |
| Text search | SQLite FTS5 | accepted | 정확 검색 |
| Vector search | sqlite-vec | candidate | 1차에서 사용 가능성 검증 필요 |
| Embedding runtime | fastembed | accepted | 로컬 embedding 실행 |
| Embedding model | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | accepted | 다국어 기본값 |
| LLM runtime | configurable endpoint | accepted | sample env 제공, provider 고정 금지 |
| Vault | Obsidian-compatible Markdown folder | accepted | 사람이 읽고 수정 |
| Non-Markdown conversion | markitdown adapter | phase-2 candidate | Markdown normalized 변환 후보. MDX는 Web preview/export optional |
| Web backend/API | FastAPI | accepted | Phase 3 Web UI 확정 stack |
| Web frontend | Server-rendered HTML + Vanilla JS + plain CSS | accepted | React/Vite/Node build 제외 |

## sample env에 포함할 설정 후보

```text
LLM_WIKI_VAULT_PATH=./vault
LLM_WIKI_DB_PATH=./data/wiki.sqlite
LLM_WIKI_LLM_PROVIDER=openai_compatible
LLM_WIKI_LLM_ENDPOINT=http://localhost:11434/v1
LLM_WIKI_CHAT_MODEL=
LLM_WIKI_EMBEDDING_BACKEND=fastembed
LLM_WIKI_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
LLM_WIKI_AUTO_APPROVE_FOR_TESTS=false
LLM_WIKI_WEB_ADMIN_USER=admin
LLM_WIKI_WEB_ADMIN_PASSWORD=change-me
```

## Planning에서 확인할 의존성 리스크

- sqlite-vec 설치/배포 방식
- fastembed 모델 다운로드/캐시 위치
- OpenAI-compatible endpoint와 Ollama/LM Studio 호환 방식
- Web UI stack 선택
- markitdown 도입 시 optional/default 여부 결정
- MDX는 Web preview/export optional format으로만 고려
- Web admin password는 실제 `.env`에서만 관리


## Phase 3 Web UI 확정 dependency

| Package | 용도 | 상태 |
|---|---|---|
| `fastapi` | Web backend/API | accepted |
| `uvicorn` | local ASGI server | accepted |
| `jinja2` | server-rendered HTML template | accepted |
| `python-multipart` | login/form/action request parsing | accepted |
| `pydantic` | request/response/settings schema validation | accepted |
| `PyYAML` | YAML settings read/write | accepted |
| `python-dotenv` | `.env` loading | accepted |

## Phase 3 frontend 결정

- server-rendered HTML을 기본으로 한다.
- interactive behavior는 Vanilla JavaScript ES modules로 구현한다.
- CSS는 plain CSS를 사용한다.
- Graph popup은 inline SVG + Vanilla JS로 구현한다.
- React/Vite/Next.js/Tailwind build pipeline은 초기 Web UI 범위에서 제외한다.

## Auth 구현 결정

- `.env` 사용자 비밀번호 기반 단일 관리자 로그인.
- session은 Python stdlib `hmac` 기반 signed cookie로 구현한다.
- 별도 auth framework/passlib/OAuth는 초기 범위에서 제외한다.
