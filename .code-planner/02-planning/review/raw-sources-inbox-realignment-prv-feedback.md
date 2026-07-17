# Raw Sources → Inbox Realignment PRV Feedback

- PRV session: `20260716T072651Z-01bdca`
- PRV URL: `http://100.66.135.34:34249/session/20260716T072651Z-01bdca`
- Review mode: Tailnet
- Reviewed at: `2026-07-16T07:33:34Z`
- User decision: confirmed

## Confirmed direction

User confirmed the realigned product flow:

```text
업로드/Raw Sources에서 가져오기
-> Inbox pending
-> LLM 확인/처리
-> Wiki 문서화 완료
-> 원본 파일 Raw Sources archive 이동
```

## Confirmed planning changes

- `Inbox` is the input queue.
- `Raw Sources` is the success archive, not the normal processing queue.
- Existing `vault/10.Raw Sources` documents are import/migration material and must be registered into Inbox before processing.
- Phase 5 is split into:
  - Phase 5A — Inbox-to-Job dispatch mapping.
  - Phase 5B — CLI/Web UI integration.
- Build must implement `inbox_item_id -> source_id -> ingest_job` materialization/linking before `/ingest` UX testing.
- UX/user testing is blocked until Phase 5A passes.

## Review result

- Approved for Build continuation from Phase 5A.
- No additional Planning changes requested.
