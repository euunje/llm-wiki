# LLM-Wiki

> 로컬에서 동작하고 LLM이 유지보수하는 개인 지식 베이스입니다. 문서를 넣어 두면, LLM이 이를 검색하고 질의할 수 있는 살아 있는 Obsidian 위키로 점진적으로 정리해 줍니다.

포크해도 좋고, 더 많은 사람에게 알려질 수 있도록 Star ⭐️도 남겨 주세요!

-------------------------
안녕하세요, 저는 AI 컨설턴트로 일하고 있는 Nihar Shrotri입니다.
현재 인공지능 및 머신러닝 박사 과정을 밟고 있습니다.

LinkedIn에서 편하게 연락 주세요: https://www.linkedin.com/in/niharshrotri/
-------------------------

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/LLM-Qwen3--14B-purple.svg)](https://ollama.com/library/qwen3)
[![Local-first](https://img.shields.io/badge/runs-100%25_local-green.svg)](#)

이 프로젝트는 Andrej Karpathy가 [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)에서 설명한 패턴을 바탕으로 합니다. 기존 RAG처럼 질의 시점에 원본 문서에서 바로 검색하는 대신, LLM이 소스를 점진적으로 **컴파일**해서 원본 문서와 사용자 사이에 구조화된 상호 연결 마크다운 위키를 만듭니다. 이 위키는 **지속적으로 누적되는 산출물**입니다. 상호 참조는 이미 연결되어 있고, 모순은 이미 표시되어 있으며, 합성된 내용은 지금까지 읽은 모든 정보를 반영합니다.

직접 위키를 작성할 필요는 없습니다. 요약, 상호 참조, 분류, 기록 관리는 모두 LLM이 맡습니다. 사용자는 자료를 넣고 질문만 하면 됩니다.

Apple Silicon 또는 Ollama가 동작하는 어떤 환경에서도 100% 로컬로 실행됩니다. API 키도, 클라우드도, 외부로 나가는 데이터도 없습니다.

## 동작 방식

```bash
# 파일 추가(PDF, markdown, HTML, DOCX, text)
wiki add ~/Documents/papers --recursive

# Qwen3가 문서를 읽고 상호 연결된 위키를 생성하는 과정 보기
wiki ingest

# 질문하기 - 컴파일된 위키를 검색하고 출처를 함께 인용함
wiki query "X에 대한 핵심 주장은 무엇인가요?"

# 지식 베이스 상태 점검
wiki lint --fix

# Obsidian에서 전체 내용을 탐색(graph view, backlinks 등)
open wiki/
```

각 ingest는 YAML frontmatter와 `[[wikilinks]]`로 연결된 `sources/`, `entities/`, `concepts/` 페이지를 생성하고, 애매하거나 운영 가이드/맵 성격인 항목은 `non_categories/` review queue에 보류합니다. 각 query는 하이브리드 BM25 + vector + LLM rerank 검색으로 상위 페이지를 찾은 뒤, 근거가 포함된 답변을 생성합니다. 각 lint 실행은 끊어진 링크, 고아 페이지, 잘못된 frontmatter, 소스의 잡음, 그리고 옵션에 따라 LLM이 찾아내는 페이지 간 모순까지 검사합니다.

## 기능

### 핵심 기능
- **점진적 ingest** - 파일을 넣고 `wiki ingest`를 실행하면 상호 연결된 source/entity/concept 페이지와 필요한 review queue 항목이 생성됩니다.
- **구조화된 후보 추출** - Qwen3가 각 소스에서 `candidate`를 추출하고 `pageKind: entity | concept | review`로 분류합니다. 운영 가이드/맵 성격 항목은 자동 페이지가 아니라 review queue로 갑니다.
- **스마트 병합** - 관련 소스를 다시 ingest하면 기존 엔티티/개념 페이지를 덮어쓰지 않고 업데이트해 계보를 보존합니다.
- **하이브리드 검색** - BM25 전문 검색 + vector embedding + LLM reranking을 모두 로컬에서 수행합니다([QMD](https://github.com/tobi/qmd) 사용).
- **3방향 질의 범위** - `Wiki`(LLM이 컴파일한 페이지 기반의 주제별 답변), `Raw`(원본 문서에서의 정확한 조회), `Hybrid`(둘 다) 중 선택할 수 있습니다.
- **의도 분류** - "hi", "thanks" 같은 가벼운 메시지는 retrieval을 건너뛰고 빠르게 응답하여, 잡담 한 번당 약 30초를 아낍니다.
- **인용 포함 합성** - 질의 결과는 각 주장에 근거가 되는 페이지를 가리키는 `[[wikilinks]]`가 포함된 마크다운 답변으로 반환됩니다.
- **Write-back** - 좋은 답변을 `--save-as`로 `synthesis/` 페이지로 저장해 탐색 결과가 지식 베이스에 누적되도록 할 수 있습니다.
- **위키 lint** - 끊어진 링크, 고아 페이지, 잘못된 frontmatter, 소스 내 잡음, 그리고 `--deep` 사용 시 페이지 간 모순까지 자동 점검합니다.
- **자동 수정** - 대부분의 스타일 문제는 한 번의 명령으로 해결됩니다.
- **자동 reindex** - ingest와 lint 이후 검색 인덱스가 자동으로 갱신되어 새 페이지를 바로 조회할 수 있습니다.

### 웹 UI
`wiki serve` 실행 후 `http://127.0.0.1:8000`에서 전체 웹 인터페이스를 사용할 수 있습니다.
- **Dashboard** - 프로젝트 통계와 최근 활동을 보여줍니다.
- **Sources** - 소스를 한 번에 목록 조회, 검토, 삭제, 재-ingest 할 수 있습니다.
- **Ingest** - 드래그 앤 드롭 업로드, 실시간 진행 로그, 탭을 닫거나 서버를 재시작해도 살아 있는 영속 작업을 지원합니다.
- **Jobs** - 모든 ingest 실행 이력과 실시간 진행률, 오류 상세를 확인할 수 있습니다.
- **Query** - 스트리밍 합성, 범위 토글, synthesis 저장 버튼이 있는 채팅형 인터페이스입니다.
- **Lint** - 한 번의 클릭으로 자동 수정할 수 있는 대화형 lint 리포트입니다.
- **Graph** - 페이지 유형별로 색이 구분된, 전체 위키의 D3 force-directed 시각화입니다.

### 지원 입력 형식
`.pdf` · `.md` · `.html` · `.docx` · `.txt`

### Obsidian 연동
`wiki/` 폴더는 다음을 갖춘 즉시 사용 가능한 Obsidian vault입니다.
- 색상으로 구분된 그래프 뷰(sources, entities, concepts, synthesis가 각각 고유 색상을 가짐)
- Dataview 플러그인과 호환되는 YAML frontmatter
- 모든 상호 참조를 네이티브 `[[wikilinks]]`로 저장하여 backlinks, outgoing links, graph traversal이 모두 동작

## 아키텍처

Karpathy의 설명을 따라 3개 계층으로 구성됩니다.

```
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   raw/        │ → │   LLM Agent   │ → │   wiki/       │
│ Your docs     │   │  (Qwen3-14B)  │   │ Markdown,     │
│ (immutable)   │   │               │   │ auto-linked   │
└───────────────┘   └───────────────┘   └───────────────┘
                          │                     │
                          ▼                     ▼
                    ┌───────────────┐   ┌───────────────┐
                    │ schema/       │   │   Obsidian    │
                    │ AGENTS.md     │   │  graph view   │
                    │ (the rules)   │   │  + editing    │
                    └───────────────┘   └───────────────┘
```

- **`raw/`** - 원본 문서입니다. 변경 불가이며, 에이전트는 읽기만 하고 수정하지 않습니다.
- **`wiki/`** - LLM이 유지보수하는 마크다운입니다. 페이지 유형별 폴더(`sources/`, `entities/`, `concepts/`, `synthesis/`, `non_categories/`)와 자동 생성되는 `index.md`, `log.md`가 있습니다. `non_categories/`는 애매한 후보, low-confidence 후보, 또는 외부 소유 guide/map 후보를 보류하는 review queue입니다. Obsidian에서 열면 됩니다.
- **`schema/AGENTS.md`** - 규칙 문서입니다. LLM이 페이지를 어떻게 포맷할지, 언제 merge와 create를 구분할지, 어떻게 인용할지, 모순을 어떻게 다룰지 알려 줍니다. 선호가 바뀌면 이 파일을 수정하면 됩니다.
- **`.wiki/`** - 내부 상태 저장소입니다. SQLite ingest 이력, QMD 검색 인덱스, 설정이 들어 있으며 git ignore 대상입니다.

### ingest 파이프라인

각 소스는 세 단계의 LLM 패스를 거칩니다.

1. **추출**(thinking mode on) - Qwen3가 소스를 읽고 요약, 핵심 요점, 태그, 그리고 `pageKind: entity | concept | review` 후보를 포함한 구조화된 JSON을 반환합니다. legacy `entities[]`/`concepts[]`도 계속 허용됩니다.
2. **페이지 작성**(streaming, thinking mode off) - entity/concept 후보마다 한 번씩 호출합니다. 새 페이지를 처음부터 작성하거나, 기존 페이지에 새 정보를 *병합*합니다. `review` 후보는 추가 LLM 호출 없이 `non_categories/`에 deterministic review note로 저장됩니다.
3. **소스 요약** - `sources/<slug>.md` 페이지를 작성해 이 소스가 건드린 모든 위키/리뷰 페이지를 provenance 용도로 나열합니다.

세 단계가 끝나면 `index.md`가 다시 생성되고, `log.md`가 추가되며, QMD의 검색 인덱스가 자동으로 갱신됩니다.

### 질의 파이프라인

1. **하이브리드 검색** - QMD를 통해 BM25 전문 검색 + vector 유사도 + LLM reranker를 로컬에서 실행합니다.
2. **Top-K 페이지 적재** - 상위 5~8개 결과의 전체 내용을 불러옵니다.
3. **합성** - Qwen3가 `[[wikilinks]]`를 사용해 페이지를 참조하는 근거 포함 마크다운 답변을 작성합니다.
4. **(선택) 저장** - `--save-as`로 답변을 새 `synthesis/` 페이지로 저장할 수 있습니다.

## 스택

| 계층 | 구성 요소 | 이유 |
|---|---|---|
| LLM | [Ollama](https://ollama.com) + [Qwen3-14B](https://ollama.com/library/qwen3:14b) Q4_K_M | 강한 추론 성능, 40K 컨텍스트, thinking mode, 디스크 9.3GB |
| 검색 | [QMD](https://github.com/tobi/qmd) (BM25 + vector + rerank) | 완전 로컬, SQLite 기반, 무거운 작업을 처리 |
| Embeddings | EmbeddingGemma-300M (QMD 통해 사용) | 작은 크기, 높은 품질 |
| Reranker | Qwen3-Reranker-0.6B (QMD 통해 사용) | 빠른 cross-encoder rerank |
| CLI | [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io) | 좋은 UX, 컬러 출력, 진행률 바 |
| 파서 | pypdf, python-docx, beautifulsoup4, lxml | 주요 문서 형식을 지원 |
| Vault | [Obsidian](https://obsidian.md) | 최고 수준의 graph view와 backlink UX를 기본 제공 |

클라우드 서비스는 없습니다. API 키도 필요 없습니다. 데이터는 기기 밖으로 나가지 않습니다.

## 요구 사항

- **Python 3.11+**
- **Node.js 18+**(QMD용)
- **Ollama**와 `qwen3:14b` 모델 사전 다운로드(~9.3GB)
- **QMD**(`npm install -g @tobilu/qmd`)
- **macOS의 Homebrew SQLite**(`brew install sqlite`)
- 모델과 embedding을 위한 **약 15GB의 여유 디스크 공간**
- **약 12GB RAM** 권장(편하게 쓰려면 16GB+)
- **Obsidian**(선택 사항이지만 탐색용으로 강력 추천)

macOS(Apple Silicon, M3 Pro 18GB)에서 테스트했습니다. Linux에서는 동작해야 하며, Windows는 미검증입니다.

## 설치

```bash
# 저장소 복제
git clone https://github.com/YOUR-USERNAME/llm-wiki.git
cd llm-wiki

# 가상 환경 생성(uv가 pip보다 빠르지만 둘 다 가능)
uv venv
source .venv/bin/activate
uv pip install -e .

# LLM 다운로드(1회, 약 9.3GB)
ollama pull qwen3:14b

# QMD 설치(검색 백엔드)
npm install -g @tobilu/qmd

# 확인
wiki version
wiki --help
```

## 빠른 시작

```bash
# 1. 원하는 폴더에 위키 생성
mkdir my-wiki && cd my-wiki
wiki init

# 2. source 문서를 raw/에 넣거나 아래처럼 추가
wiki add ~/Documents/papers --recursive

# 3. ingest 실행(기본은 대화형 - filing 전에 후보 분류 결과를 보여주고 소스별로 y/n을 묻습니다)
wiki ingest

# 첫 query 시 QMD가 embedding + reranker 모델을 다운로드합니다
# (~2GB, 1회). 이후 query는 빠릅니다.

# 4. 질문하기
wiki query "이 문서들 전반의 핵심 주제는 무엇인가요?"

# 5. 좋은 답변을 synthesis 페이지로 저장
wiki query "X와 Y를 비교해줘" --save-as x-vs-y-comparison

# 6. 상태 점검 및 자동 수정
wiki lint --fix

# 7. Obsidian에서 vault 열기
open wiki/   # 그다음 "Open folder as vault"
```

## 명령어

| 명령어 | 용도 |
|---|---|
| `wiki init [path]` | 새 위키 프로젝트 스캐폴드 생성 |
| `wiki add <file-or-folder> [-r]` | 소스를 `raw/`로 복사하고 ingest 대상으로 등록 |
| `wiki sources list` | 추적 중인 모든 소스와 상태를 표시 |
| `wiki sources show <id>` | 특정 소스의 메타데이터와 텍스트 미리보기 표시 |
| `wiki sources rm <id>` | 소스 추적에서 제거 |
| `wiki ingest [source_id]` | 3단계 LLM ingest 파이프라인 실행 |
| `wiki query "<question>" [--scope wiki\|raw\|hybrid] [--save-as <slug>]` | 검색 후 근거가 포함된 답변 합성 |
| `wiki reindex` | QMD 검색 인덱스를 강제로 다시 생성 |
| `wiki lint [--deep] [--fix]` | 위키 상태 점검 |
| `wiki status` | 프로젝트 통계, 경로, 설정, 백엔드 상태 표시 |
| `wiki serve [--port N]` | `http://127.0.0.1:8000`에서 웹 UI 실행 |

모든 명령어의 전체 옵션은 `wiki <command> --help`로 확인할 수 있습니다. 전체 사용 흐름은 [USAGE.md](./USAGE.md)를 참고하세요.

## 예시 출력

`notes.txt`(Qwen3에 대한 28단어 메모)를 ingest한 실제 예시입니다.

```
Source #1  raw/notes.txt
  parsing…
  extracting entities and concepts (thinking mode)…

Title: Quick Notes on Qwen
Slug:  quick-notes-on-qwen

Summary:
  Qwen is a family of large language models developed by Alibaba Cloud.
  The latest version, Qwen3, introduces a thinking mode designed to enhance
  performance on complex reasoning tasks.

Entities (3):
  + alibaba-cloud (organization)  Alibaba Cloud
  + qwen (product)                Qwen
  + qwen3 (product)               Qwen3

Concepts (2):
  + large-language-models                 Large Language Models
  + thinking-mode-for-complex-reasoning   Thinking Mode for Complex Reasoning

File these? Will create/update ~6 wiki pages. [Y/n]: Y

created entity alibaba-cloud
created entity qwen
created entity qwen3
created concept large-language-models
created concept thinking-mode-for-complex-reasoning
created source  quick-notes-on-qwen

✓ Ingested Quick Notes on Qwen — 6 created, 0 updated
```

이렇게 **28단어 입력에서 6개의 상호 연결된 페이지**가 생성됩니다. 각 페이지에는 YAML frontmatter, 서로를 가리키는 `[[wikilinks]]`, 그리고 소스로 되돌아가는 provenance가 들어 있습니다. Obsidian의 graph view를 열면 해당 클러스터가 시각적으로 드러납니다.

11개 페이지를 ingest한 뒤의 실제 query 예시입니다.

```
> wiki query "how does multi-head attention differ from self-attention?"

  searching wiki (BM25 + vector + rerank)…
  found 8 relevant page(s):
    1. 0.93 concepts/multi-head-attention.md      Multi-Head Attention
    2. 0.55 concepts/self-attention-mechanism.md  Self-Attention Mechanism
    3. 0.40 entities/attention-is-all-you-need.md Attention is All You Need
    ...

  synthesizing answer…

Multi-head attention and self-attention are related but distinct mechanisms:

1. **Scope and Parallelism**
   - Self-attention is a single mechanism where each position in the input
     computes attention weights based on all other positions
     [[concepts/self-attention-mechanism]].
   - Multi-head attention extends this by using multiple parallel attention
     heads, allowing the model to focus on diverse patterns simultaneously
     [[concepts/multi-head-attention]].

2. **Information Capture**
   - Self-attention focuses on a single representation.
   - Multi-head aggregates information from multiple heads, each capturing
     different aspects (syntactic vs semantic, etc.)
     [[concepts/multi-head-attention]].

[... etc.]
```

모든 주장은 인용됩니다. 모든 인용은 실제로 존재하는 페이지를 가리킵니다.

## lint 예시

```
> wiki lint

╭─────────── Lint Report ────────────╮
│ Health score: 57/100               │
│ Pages checked: 12                  │
│                                    │
│   2 errors · 21 warnings · 0 infos │
╰────────────────────────────────────╯

──── Errors (2) ────

  synthesis/transformers-and-llms.md
    ✗ broken_wikilink: Broken wikilink: [[entities/introduction-to-transformers]]
      → Either create the page or remove the link.

──── Warnings (21) ────

  entities/qwen.md
    ! malformed_wikilink: 'sources/quick-notes-on-qwen.md' should be
      'sources/quick-notes-on-qwen'
      ✓ auto-fixable

  [... 20 more warnings ...]

> wiki lint --fix
✓ auto-fixed: 11

> wiki lint
╭─────────── Lint Report ───────────╮
│ Health score: 100/100             │
│   0 errors · 0 warnings · 0 infos │
╰───────────────────────────────────╯
✓ No issues found. Your wiki is in good shape!
```

## 프로젝트 상태

**현재 버전: v0.8.1** - 개인용으로는 실사용 가능한 상태입니다.

| 단계 | 범위 | 상태 |
|---|---|---|
| 1 | 스캐폴딩, CLI, Obsidian vault 설정 | ✅ 완료 |
| 2 | 파서(PDF, MD, HTML, DOCX, TXT), dedupe, `wiki add` | ✅ 완료 |
| 3 | LLM ingest 파이프라인(3 pass, streaming, merge 경로) | ✅ 완료 |
| 4 | QMD 검색 + 인용이 포함된 `wiki query` + save-back | ✅ 완료 |
| 5 | lint 검사 + 자동 수정 + 심층 모순 탐지 | ✅ 완료 |
| 6 | FastAPI + HTMX 웹 UI(7개 페이지: Dashboard, Sources, Ingest, Jobs, Query, Lint, Graph) | ✅ 완료 |
| 7 (v0.7.0) | Source CRUD, 의도 분류, 3방향 scope 전환 | ✅ 완료 |
| 8 (v0.8.0) | 영속 ingest 작업(탭 닫기, 서버 재시작에도 유지) | ✅ 완료 |
| 8.1 | ingest 및 lint 후 자동 reindex | ✅ 완료 |

### 향후 가능 작업
- Hugging Face Spaces 배포(더 작은 모델, API 호환)
- 활성 작업 수를 실시간으로 보여주는 Dashboard
- 위키 공유용 정적 HTML 내보내기
- 다중 사용자 / 팀 기능
- 모바일 친화적 웹 UI
- 미세 조정된 query expansion 모델
- 추출된 주장별 confidence scoring
- 스캔된 PDF용 OCR 지원
- EPUB 지원

## 크레딧

- **[Andrej Karpathy](https://karpathy.ai/)** - [이 gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)에 설명된 LLM-Wiki 패턴의 제안자입니다. 이 프로젝트는 그 아이디어를 직접 구현한 것입니다.
- **[QMD](https://github.com/tobi/qmd)** by Tobi Lütke - query-time retrieval에서 핵심 역할을 하는 하이브리드 검색 백엔드입니다.
- **[Qwen3](https://qwenlm.github.io/blog/qwen3/)** by Alibaba Cloud - 읽기, 쓰기, 합성을 담당하는 로컬 LLM입니다.
- **[Ollama](https://ollama.com)** - Apple Silicon에서 로컬 LLM 추론을 쉽게 해 주는 런타임입니다.
- **[Obsidian](https://obsidian.md)** - 직접 graph view를 만들 필요가 없게 해 준 도구입니다.

## 라이선스

MIT - [LICENSE](LICENSE)를 참고하세요.

---

*"지식 베이스를 유지하는 데 가장 지루한 부분은 읽기나 사고가 아니라 기록 관리입니다. 사람은 유지보수 부담이 가치보다 빠르게 커지면 위키를 포기합니다. LLM은 지루해하지도 않고, 상호 참조 업데이트를 잊지도 않으며, 한 번에 15개 파일을 처리할 수 있습니다."*
— Karpathy
