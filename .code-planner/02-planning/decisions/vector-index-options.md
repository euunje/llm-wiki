# Vector Index Direction Check

## 배경

기존 계획은 SQLite + sqlite-vec를 우선 후보로 두었다. 하지만 sqlite-vec 설치 실패 시 단순 fallback으로 넘기기보다, Build 전에 방향을 사전 검토하기로 했다.

## 결정 상태

- 현재 확정: embedding row 저장은 필수
- 현재 미확정: vector similarity index 구현 방식
- fallback을 무작정 두지 않고, Build 초기에 옵션을 비교한다.

## 검토 옵션

| 옵션 | 장점 | 단점 | 적합한 경우 |
|---|---|---|---|
| sqlite-vec | SQLite 안에서 일관된 저장/검색 | 설치/환경 이슈 가능 | 로컬 단일 DB 유지가 중요할 때 |
| sqlite-vss | SQLite 기반 vector search 대안 | 유지보수/호환성 확인 필요 | sqlite-vec가 맞지 않을 때 |
| LanceDB | vector 검색 기능 강함 | SQLite 외 추가 저장소 | vector 품질/성능 우선일 때 |
| 파일/메모리 brute-force | 구현 단순, fallback 쉬움 | 규모 커지면 느림 | 초기 smoke test/소규모 자료 |
| FTS only phase-1 | 안정적 | 의미 검색 없음 | Phase 1에서 vector index를 미룰 때 |

## 추천 방향

Build 시작 시 spike를 먼저 수행한다.

1. sqlite-vec 설치/로드 가능성 확인
2. fastembed 결과 dimension 확인
3. 100개 이하 sample vector insert/search smoke test
4. 실패 시 sqlite-vss/LanceDB/파일 brute-force 중 하나를 사용자에게 보고 후 선택

## Build handoff 반영

- Phase 1에서 embedding row 저장은 required
- vector similarity index는 `vector-index-spike` 결과로 최종 결정
- `wiki doctor`는 vector index backend 상태를 report해야 한다.
