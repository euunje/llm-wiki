# CLI E2E Test Plan — Phase 1

## 목적

Build에서 구현되어야 할 목표를 기능별 E2E 테스트로 명확히 한다.

## 공통 E2E 조건

- 모든 테스트는 임시 workspace에서 실행한다.
- 실제 secret은 사용하지 않는다.
- LLM 연결 테스트는 sample env 또는 test endpoint를 사용한다.
- 파일/DB 변경 명령은 결과 artifact 또는 report를 남긴다.
- `--json` 모드는 핵심 명령에서 smoke test한다.

---

## E2E-01. Init

```text
wiki init --path ./tmp-wiki
```

기대 결과:

- `vault/00_Inbox`, `vault/10_Wiki`, `vault/20_Review`, `vault/80_Raws`, `vault/90_Settings` 생성
- `data/wiki.sqlite`, `data/raw`, `data/normalized`, `data/artifacts` 생성
- YAML settings 생성
- 재실행 시 idempotent

Pass:

- 필수 폴더/DB/settings가 존재하고 재실행해도 손상 없음

---

## E2E-02. Markdown ingest pipeline

```text
wiki ingest samples/rag.md
wiki normalize <source_id>
wiki chunk <source_id>
wiki status --json
```

기대 결과:

- Source row 생성
- normalized Markdown 생성
- SourceChunk row 생성
- status에서 source/chunk 상태 확인

Pass:

- Source → normalized → chunked 상태 전이가 DB와 artifact로 확인됨

---

## E2E-03. Unsupported input guard

```text
wiki ingest samples/paper.pdf
wiki ingest https://example.com/article
```

기대 결과:

- Phase 1에서는 unsupported 또는 Phase 2 안내 반환
- 처리된 것처럼 Source를 잘못 만들지 않음

Pass:

- 명확한 error/warn과 exit code가 있음

---

## E2E-04. Embedding

```text
wiki embed source:<source_id>
```

기대 결과:

- chunk embedding 생성
- model name, dimension, target 저장
- sqlite-vec index 갱신 또는 갱신 예정 report

Pass:

- embedding row와 dimension 확인 가능

---

## E2E-05. LLM 연결 테스트

```text
wiki models list
wiki models test <chat_model_id>
wiki models test <embedding_model_id>
```

기대 결과:

- 등록된 provider/model 표시
- chat model sample prompt 응답 확인
- embedding model sample vector/dimension 확인
- 성공/실패 artifact 저장

Pass:

- LLM 연결 테스트 위치가 `wiki models test`로 명확함
- 실패 시 endpoint/auth/model 오류가 report됨

---

## E2E-06. LLM candidate contract

```text
wiki extract-claims <source_id> --json
```

Phase 1 기대 결과:

- 실제 품질보다 JSON/artifact 계약 검증
- JSON parse/schema validation 수행
- 실패 시 error artifact와 retry 후보 생성

Pass:

- artifact path, run id, validation result가 출력됨

---

## E2E-07. Sync dry-run/apply

```text
wiki sync
wiki sync --apply
```

기대 결과:

- 기본 `wiki sync`는 read-only dry-run report
- `--apply`에서만 반영
- 반영 결과 artifact 저장

Pass:

- dry-run에서 파일/DB 변경 없음
- apply 후 변경 요약과 artifact 존재

---

## E2E-08. Retry with instruction

```text
wiki retry <run_id> --instruction "태그 범위를 더 좁혀 다시 판단"
```

기대 결과:

- 이전 후보는 `superseded`
- 새 run 생성
- retry_instruction이 run metadata에 기록
- 새 artifact 생성

Pass:

- 이전 후보와 새 후보 연결 추적 가능

---

## E2E-09. Compile placeholder

```text
wiki compile concept:<concept_id>
```

Phase 1 기대 결과:

- 기본 초안 또는 placeholder WikiPage preview 생성
- 실사용 품질은 Phase 2

Pass:

- preview path 또는 artifact가 생성됨

---

## E2E-10. Healthcheck

```text
wiki healthcheck --json
```

기대 결과:

- DB/Vault 불일치
- stale embedding
- orphan concept
- broken link
- failed jobs 누적 상태 report

Pass:

- 시스템 데이터 상태를 한 번에 확인 가능

---

# Phase 1 완료 기준

다음이 모두 pass이면 Phase 1 CLI foundation 완료로 본다.

- E2E-01 Init
- E2E-02 Markdown ingest pipeline
- E2E-04 Embedding
- E2E-05 LLM 연결 테스트
- E2E-06 LLM candidate contract
- E2E-07 Sync dry-run/apply
- 공통 CLI 계약: `--json`, exit code, artifact/report
