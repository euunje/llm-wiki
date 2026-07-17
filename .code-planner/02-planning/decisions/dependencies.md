# Dependencies and Affected Areas

## Source areas

- `src/llm_wiki/config.py`
  - Inbox/Failed/Review/Raw archive path mapping 확장.
  - `processing`은 path가 아니라 DB state/lock.
- `src/llm_wiki/db.py`
  - `inbox_items`, `inbox_events`, candidate/review state 또는 equivalent schema.
- `src/llm_wiki/ingest_raw.py`
  - raw 등록 중심에서 Raw Sources import-to-Inbox 및 archive move 지원으로 조정.
- `src/llm_wiki/ingest_llm.py`
  - Inbox item 처리, chunked extraction, archive move, failed/review routing 연동.
- `src/llm_wiki/jobs.py`
  - `inbox_item_id -> source_id -> job` 연결, chunk progress, state events 지원.
- `src/llm_wiki/webapp/routes/ingest.py`
  - upload/paste/start 흐름을 Inbox-first로 변경. `scan`은 Raw queue 등록이 아니라 Raw Sources에서 Inbox로 가져오기.
- `src/llm_wiki/webapp/routes/inbox.py`
  - Review/Failed workbench 확장.
- `src/llm_wiki/webapp/templates/ingest.html`, `inbox.html`, `jobs.html`
  - 기존 UX 기반 확장.
- `src/llm_wiki/cli.py`
  - `add`, `ingest`, `status`, `retry` 의미 조정.
- tests
  - inbox state, file move, failed/review routing, chunked extraction, UI/API, CLI tests 추가.

## External dependencies

- 신규 외부 서비스/API/결제/auth 의존성 없음.
- 기존 LLM provider/LM Studio context overflow 대응은 chunked extraction으로 해결한다.

## Path conventions

- Input conventions: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- Work queues: `Inbox/_Failed`, `Inbox/_Review`.
- Archive: Raw Sources.
- Existing Raw Sources material: import/migration input only; after import it must appear as Inbox pending before processing.
- No physical `Inbox/_Processing` folder.

## Critical mapping dependency

- Current code may create `inbox_items` with `source_id = NULL` while existing job/LLM code expects `sources.id`.
- Phase 5A must add the mapping layer:
  1. create/reuse `sources` row for an Inbox item at processing start,
  2. set `inbox_items.source_id`,
  3. enqueue existing job by `source_id`,
  4. preserve Inbox state transitions and archive/failed/review movement.
