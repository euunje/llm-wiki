# Feature Contract — Chunked extraction map-reduce

## 목적

큰 문서에서 LLM context overflow 없이 entity/concept 후보를 추출한다.

## 현재 문제

parser는 `ParsedDocument.chunks`를 만들지만 현재 extraction은 `parsed.text`를 잘라 사용한다. 이 방식은 뒤쪽 정보를 잃고 LM Studio context overflow를 유발한다.

## 목표 흐름

```text
ParsedDocument.chunks
→ chunk-level extraction
→ candidate/summary aggregation
→ conservative resolution
→ page generation
```

## Chunk output

- chunk_index
- chunk_summary
- candidates
- key_takeaways
- confidence
- optional char range/page metadata

## Aggregation rules

- 같은 mention/slug 후보 dedupe
- chunk frequency와 confidence를 모은다.
- conflicting candidates는 review로 보낸다.
- final extraction은 기존 2-pass resolution에 연결한다.

## Fallback rules

- 작은 문서는 single extraction 가능.
- context overflow 400 또는 문서 길이 기준 초과 시 chunked extraction.
- chunk 일부 실패 시 retry 후, 계속 실패하면 source/item은 failed 또는 partial review로 라우팅한다.

## Acceptance criteria

- 긴 문서가 context overflow 없이 처리된다.
- 뒤쪽 chunk의 entity/concept도 누락되지 않는다.
- chunked 결과가 source page summary에 반영된다.
