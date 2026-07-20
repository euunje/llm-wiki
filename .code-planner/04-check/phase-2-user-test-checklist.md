# Phase 2 User Functional Test Checklist

Phase 2 산출물의 품질 평가는 휴리스틱 기반이며 `gold_available: false`이므로 사용자 검토가 필요합니다.

## 실행 환경

```bash
PYTHONPATH=src python3 -m llm_wiki.cli init --path /tmp/opencode/phase2-usertest --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest samples/rag.md --path /tmp/opencode/phase2-usertest --json
PYTHONPATH=src python3 -m llm_wiki.cli normalize <source_id> --path /tmp/opencode/phase2-usertest --json
PYTHONPATH=src python3 -m llm_wiki.cli chunk <source_id> --path /tmp/opencode/phase2-usertest --json
```

## 점검 항목

| # | 명령 | 확인 기준 |
|---|---|---|
| 1 | `wiki extract-claims <source_id>` | 후보 envelope이 생성되고 `validation.ok == true`, `candidate_count >= 2`, `quality_evaluation.overall_score > 0`. `node_candidates[].summary`가 한국어인지, title이 일반적이지 않은지. |
| 2 | `wiki map <source_id>` | `mapping_candidates`에 유효한 `mapping_action`이 있고 `quality_evaluation.scores.mapping_quality == 1.0`. 매핑 이유가 한국어로 설명되는지. |
| 3 | `wiki retry <candidate_id> --instruction "..."` | 새 `superseded_by` 행이 생기고 기존 후보는 `superseded`. |
| 4 | `wiki summarize source:<source_id>` | 요약이 한국어 중심이며 `RAG`, `LLM`, `OpenCode`, `Claude Code` 같은 기술 용어가 그대로 보존되는지. |
| 5 | HTML 변환 (임시 HTML 파일) | `<h1>RAG</h1><p>RAG와 LLM의 token overhead를 비교한다.</p>` 같은 입력이 변환되어 normalized Markdown이 생성되는지. |
| 6 | `wiki search "RAG"` | `metadata.vector.attempted`가 true 인지, 결과에 `match_type: fts` 또는 `vector_*_fallback`이 포함되는지. |
| 7 | `wiki compile source:<source_id>` | preview_path의 Markdown이 frontmatter, 한국어 설명, 기술 용어 보존을 만족하는지. |
| 8 | `prompt_versions` 조회 | `extract_claims`, `map`, `link`, `summarize`, `compile`, `ask` 6개가 `confirmed` 상태인지. |

## 결정

- 한국어 설명이 자연스럽고, 영어 기술 용어가 그대로 보존되면: 승인
- 일부 표현이 어색하면: fix 요청
- 빈약하면: blocked

승인 또는 보완 요청 시 `/check phase-2` 재실행으로 commit 흐름 진행.
