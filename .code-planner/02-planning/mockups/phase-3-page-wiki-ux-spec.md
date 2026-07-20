# Phase 3 Page UX Spec — Wiki

## Review status

- Status: `drafted_review_pending`
- Scope: Wiki read/browse UX fix
- Global UX: PC-first, tablet/mobile responsive, icon + short label + 1-line helper 중심

## User decisions applied

- Wiki list는 카드 UX가 아니라 목차형 list로 구성한다.
- 본문은 Markdown 원문이 아니라 Markdown viewer로 렌더링한다.
- frontmatter는 본문 상단에 노출하지 않는다.
- 본문 상단에는 파일 위치를 제공한다.
- 모바일에서는 리스트에서 선택 후 세부 내용을 크게 보는 구조를 사용한다.
- 모바일에서는 왼쪽 목차 버튼을 눌러 목차에서 선택하고, 검색도 지원한다.
- Graph는 화면 우상단이 아니라 본문 맨 아래에 배치한다.

## 1. 페이지 목적

Wiki 페이지는 확정된 wiki 문서를 읽고, 검색하고, 관계를 따라 탐색하는 화면이다.

사용자가 이 페이지에서 하는 일:

1. wiki 목차에서 문서 선택
2. wiki 검색
3. Markdown viewer로 본문 읽기
4. 파일 위치 확인
5. 관계 graph 확인
6. graph/relation을 통해 관련 문서로 이동

사용자가 이 페이지에서 하지 않는 일:

- LLM 후보 검토
- Mapping 결정
- Inbox 처리 시작

## 2. PC 기본 화면 구조

```text
┌──────────────────────────────────────────────────────────────┐
│ Wiki                                                         │
│ 📚 확정된 wiki 문서를 읽고 관계를 탐색합니다.                  │
├──────────────────────────────────────────────────────────────┤
│ Left: Wiki TOC/List        │ Right: Document reader           │
│ - search                   │ - title                          │
│ - folder/tree style list   │ - file path                      │
│ - compact rows             │ - rendered markdown body          │
│                            │ - metadata/details                │
│                            │ - graph at bottom                 │
└──────────────────────────────────────────────────────────────┘
```

## 3. 모바일/태블릿 구조

모바일에서는 본문을 크게 보는 것이 우선이다.

```text
┌──────────────────────────────┐
│ Wiki                         │
│ [☰ 목차] [Search]            │
├──────────────────────────────┤
│ Selected document title       │
│ file path                     │
│ rendered markdown body        │
│ ...                           │
│ graph at bottom               │
└──────────────────────────────┘
```

목차 버튼 동작:

- `☰ 목차` 클릭
- drawer/bottom sheet로 wiki 목차 표시
- 검색 input 포함
- 문서 선택 시 drawer 닫힘
- 선택한 문서 본문을 크게 표시

Tablet:

- 충분히 넓으면 PC처럼 2-column
- 좁으면 모바일처럼 목차 drawer 사용

## 4. 왼쪽/목차 — Wiki TOC

목적: 카드가 아니라 문서 목차처럼 빠르게 탐색한다.

표시:

- title
- folder/path hint
- optional relation count
- optional updated time

형태:

```text
10_Wiki/concepts
  RAG
  Vector Search
  LLM Agent

10_Wiki/pages
  RAG Overview
  Agentic RAG
```

검색:

- title
- alias
- path
- 본문 summary 또는 heading, 가능하면

선택 상태:

- 현재 선택 문서 highlight
- 모바일에서는 선택 후 drawer 닫기

## 5. 본문 — Document reader

목적: wiki 문서를 Markdown viewer로 읽기 좋게 보여준다.

상단:

```text
RAG
vault/10_Wiki/concepts/rag.md
[Copy path] [Open raw] optional
```

본문:

- Markdown 렌더링
- heading, list, code, quote 지원
- internal link 클릭 가능
- raw markdown은 details/toggle 안에만 표시

frontmatter:

- 본문 상단에 노출하지 않음
- 필요 시 `Metadata` 접힘 영역에서 표시

metadata/details:

- aliases
- tags
- source count
- last updated
- raw frontmatter, optional collapsed

## 6. Graph 위치와 동작

Graph는 본문 맨 아래에 둔다.

목적:

- 본문을 다 읽은 뒤 관계를 확인
- 관련 문서로 이동

표시:

```text
Related graph
[RAG] --uses--> [Vector Search]
[RAG] --uses--> [LLM]
[Agentic RAG] --specializes--> [RAG]
```

동작:

- relation/node 클릭 시 해당 wiki 문서로 이동
- 클릭 대상이 없는 후보 관계면 Mapping으로 이동 가능
- PC에서는 graph + relation list
- 모바일에서는 relation list 우선, graph는 작게 또는 접힘

## 7. Empty/Error 상태

### No wiki pages

```text
아직 확정된 wiki 문서가 없습니다.
[Open Inbox] [Open Mapping]
```

### Document not found

```text
문서를 찾을 수 없습니다.
[Back to Wiki list]
```

### Markdown render failed

```text
Markdown을 렌더링하지 못했습니다.
[Show raw markdown]
```

### Graph empty

```text
연결된 관계가 아직 없습니다.
[Open Mapping]
```

## 8. 필요한 API 초안

```text
GET /api/wiki/pages
GET /api/wiki/pages/{concept_id}
GET /api/wiki/pages/{concept_id}/graph
GET /api/wiki/search?q=...
```

응답에는 가능하면 다음 정보 포함:

- title
- path
- aliases
- rendered markdown 또는 markdown source
- frontmatter metadata
- relation summary
- graph nodes/edges

## 9. 승인 기준

- PC에서 목차형 list + 본문 reader 구조가 명확하다.
- 모바일에서 목차 버튼/검색으로 문서를 고르고 본문을 크게 볼 수 있다.
- Markdown이 원문 그대로가 아니라 viewer로 렌더링된다.
- frontmatter가 본문 상단에 노출되지 않는다.
- 본문 상단에 파일 위치가 보인다.
- graph는 본문 맨 아래에 있다.
- graph/relation 클릭으로 관련 wiki로 이동할 수 있다.

## 10. 확인 필요

- 현재 없음. Wiki UX는 요청사항을 기준으로 임시 확정 가능하다.
