# Phase Check Fix Request — 2-pass generation

## 1. 문제 대상 (Problem target)

- 파일: `src/llm_wiki/ingest_llm.py`
- 영향 흐름:
  - `ingest_source()` 본문, 특히 post-commit 영역 (대략 line 1419–1473)
  - `_generate_page_content()` retry/legacy fallback 영역 (대략 line 651–713)

## 2. 문제 사유 (Reason)

`check-code-stability` 검토에서 다음 세 가지 결함이 발견되었습니다.

- **STAB-001 (bloker, transactional regression)**
  페이지가 `shutil.copy2`로 commit되고 `rebuild_index`/`append_log_entry`까지 실행된 다음에야 `_lint_changed_pages`가 실행됩니다. lint error가 남아 있으면 이미 wiki 상태는 새 페이지를 포함하고 `index.md`/`log.md`가 그 변경을 기록했는데, 동시에 DB source status는 `"error"`로 표시되고 `IngestResult.error`도 채워집니다. 모듈 docstring의 “pages are staged and only committed to wiki/ on success” 약속과 모순됩니다.

- **STAB-002 (high, retry safety)**
  LLM이 truncation/prose-only 답변을 반환해 JSON parse가 실패하면 control은 retry 없이 곧바로 `page_writer.strip_llm_noise(full)` legacy fallback으로 떨어집니다. 이 경로에서는 `links_used`/allowed_links/source 검증이 전혀 일어나지 않으므로 “확실하지 않으면 needs_review” 정책이 깨집니다.

- **STAB-003 (high, broad except)**
  `_generate_page_content()`의 `except ValueError:` 블록이 `_parse_generated_page`뿐 아니라 stream 안의 `callbacks.on_stream_chunk`가 던지는 `ValueError`(예: Rich/CLI가 닫힌 stream에서 bailout)까지 잡아 “JSON parse 실패”로 잘못 분류합니다. 결과적으로 callback 예외가 wiki 페이지 작성으로 가려지고 caller에게는 `result.ok = True`로 보입니다.

## 3. 개선 스펙 (Improvement spec)

다음 세 가지를 모두 만족해야 합니다.

- STAB-001
  - lint 검사는 staged 디렉터리 안의 staged 파일에 대해서 수행합니다. 즉, `_lint_changed_pages`를 commit 이전 단계에서 호출하고, 결과가 clean할 때만 `shutil.copy2`가 실행됩니다.
  - 또는, post-commit lint를 advisory로 강등합니다. 남은 lint error는 ingest 결과를 error로 만들지 않고, `IngestResult.error`/`changes`에는 남기지 않고 별도 필드(예: `lint_warnings`)에 기록하거나 `callbacks.on_error`로만 알립니다.
  - 어느 방향이든, 위 동작은 사용자 승인 정책(“복구 시도 후 안되면 에러”)을 그대로 반영해야 합니다. 즉 1순위는 staged 영역에서 auto-fix 시도, 2순위는 남은 error에 대해 ingest error.

- STAB-002
  - `_parse_generated_page`가 `ValueError`로 실패할 때도 1회 retry를 합니다. retry prompt는 기존 `PAGE_JSON_RETRY_TEMPLATE`을 그대로 사용하고, `validation_errors` 자리에 parse error 메시지를 채워 전달합니다.
  - retry 후에도 parse 실패가 지속되면, validation 실패와 동일하게 신규 page는 `_stage_review_candidate_file`로 review fallback, 기존 page merge/update는 ingest error로 종료합니다.
  - legacy markdown fallback은 제거하거나 “retry가 모두 실패한 후”의 최후 수단으로만 유지하되 그 경우에도 `links_used`/`allowed_links`/`source`를 강제 검증해 통과하지 못하면 review fallback으로 보냅니다.

- STAB-003
  - stream 루프에서 callback 예외(`callbacks.on_stream_chunk`)는 그대로 caller로 전파합니다. 즉 `_parse_generated_page` 호출은 별도 `try/except`로 분리해 callback 예외가 parse 실패로 오분류되지 않도록 합니다.
  - 분리 후, `_parse_generated_page`의 `ValueError`는 명시적으로 catch해 retry/review 로직으로 보냅니다.

## 4. 권장 빌드 에이전트 (Suggested build agent)

- `build-core-dev`

## 5. 필요 검증 (Validation required)

- `./.venv/bin/python -m py_compile src/llm_wiki/ingest_llm.py`
- `./.venv/bin/python -m pytest tests/test_two_pass_generation.py tests/test_phase2_candidates_schema.py -k "not test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks"`
- 새 회귀 테스트 추가:
  - STAB-001: staged 단계에서 lint error가 나면 commit이 일어나지 않고 source status가 “error”로 기록되는 시나리오
  - STAB-002: JSON parse 실패가 1회 retry 후 성공하는 시나리오, retry 후에도 실패하면 신규 page는 `non_categories/<slug>.md`로 review fallback되는 시나리오
  - STAB-003: stream callback이 `ValueError`를 던지면 그 예외가 caller로 그대로 전파되고 `IngestResult.error`로 surface되는 시나리오
- `./.venv/bin/python -m pytest tests/ -k "not test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks"` (full 회귀)

## 6. 합격 기준 (Acceptance criteria)

- 위 셋의 STAB 항목이 모두 해소되어 `check-code-stability`가 더 이상 blocker를 보고하지 않음.
- 회귀 테스트 3건 모두 통과.
- 전체 테스트(qmd long-running 제외) 모두 통과.
- transactional discipline(docstring 약속)이 다시 성립: 실패 ingest에서 새 page가 wiki/에 남지 않거나, 남더라도 명시적으로 표시되며 index/log/DB status가 일관됨.