# Init Folder Structure Contract — Phase 1

## 목적

`wiki init`이 생성해야 할 기본 폴더 구조를 Build 전에 명확히 고정한다.  
구조는 사람이 Obsidian에서 보기 쉬운 Vault 영역과, 시스템이 관리하는 data 영역을 분리한다.

## 설계 원칙

- Vault는 사람이 읽고 수정하는 영역이다.
- data는 시스템이 원본, normalized text, artifact, DB를 관리하는 영역이다.
- Obsidian에서 자주 보는 폴더는 숫자 prefix로 정렬한다.
- 원본/로그/설정은 지식 문서와 섞이지 않게 뒤쪽 번호를 쓴다.

## 추천 기본 구조

```text
llm-wiki-local/
  vault/
    00_Inbox/
      memo/
      files/
      text/
    10_Wiki/
      concepts/
      sources/
      claims/
      pages/
    20_Review/
      candidates/
      mapping/
      rejected/
    80_Raws/
      README.md
    90_Settings/
      templates/
      prompts/
      ontology/

  data/
    wiki.sqlite
    raw/
    normalized/
    artifacts/
    exports/
    cache/
```

## 폴더별 역할

| 경로 | 역할 | 사람이 직접 수정? | 시스템 쓰기? |
|---|---|---:|---:|
| `vault/00_Inbox/memo/` | 사용자가 빠르게 적는 메모 | yes | scan/read |
| `vault/00_Inbox/files/` | 사용자가 넣는 입력 파일 참조 또는 안내 | yes | scan/read |
| `vault/00_Inbox/text/` | 직접 입력 텍스트 초안 | yes | scan/read |
| `vault/10_Wiki/concepts/` | 확정된 Concept 문서 | yes | 승인 후 write |
| `vault/10_Wiki/sources/` | Source stub/요약 | yes | 승인 후 write |
| `vault/10_Wiki/claims/` | Claim 문서 또는 claim view | 제한적 | 승인 후 write |
| `vault/10_Wiki/pages/` | compile된 WikiPage | yes | 승인 후 write |
| `vault/20_Review/candidates/` | 검토 대기 후보의 사람이 보는 view | 제한적 | write |
| `vault/20_Review/mapping/` | mapping review용 view | 제한적 | write |
| `vault/20_Review/rejected/` | reject/retry 이력 view | 제한적 | write |
| `vault/80_Raws/` | 원본 파일 위치 안내 또는 사람이 볼 raw index | no 권장 | minimal |
| `vault/90_Settings/templates/` | Markdown template | yes | read/write |
| `vault/90_Settings/prompts/` | prompt confirmed/test version view | yes | write |
| `vault/90_Settings/ontology/` | ontology rule 문서 view | yes | write |
| `data/wiki.sqlite` | DB | no | yes |
| `data/raw/` | 실제 원본 저장 | no | yes |
| `data/normalized/` | normalized Markdown 저장 | no | yes |
| `data/artifacts/` | LLM JSON, logs, validation 결과 | no | yes |
| `data/exports/` | export/backup 산출물 | no | yes |
| `data/cache/` | embedding/model/cache | no | yes |

## `80_Raws`와 `data/raw`의 차이

- `data/raw/`: 실제 원본 파일이 저장되는 시스템 영역
- `vault/80_Raws/`: Obsidian에서 원본 목록/링크/주의사항을 볼 수 있는 문서 영역

즉, 대용량 원본은 `data/raw/`에 두고, 사람이 보는 raw index만 Vault에 둔다.

## `wiki init` 동작

`wiki init`은 다음을 수행한다.

1. 위 폴더 구조 생성
2. `data/wiki.sqlite` 생성
3. YAML settings 생성
4. 기본 templates/prompts/ontology placeholder 생성
5. `.env.sample` 안내 또는 생성
6. 재실행 시 기존 파일을 덮어쓰지 않고 missing path만 보완

## 검증 기준

- `wiki init` 실행 후 모든 필수 폴더가 존재한다.
- 재실행해도 기존 문서/DB가 손상되지 않는다.
- Vault 영역과 data 영역의 역할이 settings에 기록된다.
