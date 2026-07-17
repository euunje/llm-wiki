# 01 Ideation Living Note — Inbox-first ingest flow

```json
{
  "projectName": "llm-wiki inbox-first ingest flow",
  "currentStage": 5,
  "totalScore": 9,
  "planningReadiness": "ready",
  "stageCards": [
    {
      "stage": 1,
      "name": "왜 시작했나",
      "score": 2,
      "status": "충분",
      "summary": "현재 흐름은 Raw Sources -> ingest -> Wiki 중심이라 Inbox가 입력/검토의 중심 역할을 하지 못한다. 큰 문서 chunk 처리와 review/failure 상태도 Raw/Wiki 경계와 섞여 있다. 사용자는 Inbox를 입력 지점으로 두고 Raw Sources를 처리 완료 원본 archive로 재정의하려 한다.",
      "requestType": "improvement",
      "trigger": "큰 문서 ingest 중 context overflow와 현재 raw-first 구조의 한계 발견",
      "userIntent": "문서/Markdown/붙여넣기 입력을 Inbox에서 받고, ingest 후 Wiki와 Raw archive로 안전하게 분리하는 구조를 정리",
      "background": "2-pass generation, chunked extraction, needs_review routing 논의 중 입력/보관/검토 경계가 불명확함을 확인",
      "urgency": "현재 2-pass check/commit 전 사용자 기능 테스트가 막혀 있어 구조 재정의가 필요"
    },
    {
      "stage": 2,
      "name": "어떤 답을 찾나",
      "score": 2,
      "status": "충분",
      "summary": "목표는 전체 ingest 흐름을 Inbox-first로 재정비하는 것이다. 입력은 문서파일, Obsidian/Markdown 스크랩, 사용자 붙여넣기 텍스트 3유형으로 나누고, 성공한 원본은 Raw Sources archive로 이동한다.",
      "targetAnswer": "Inbox, processing, review/failed, Wiki, Raw archive의 역할과 이동 정책",
      "expectedResult": "02 Planning에서 전체 흐름 재정비 범위를 잡을 수 있는 구조 결정 문서",
      "answerDirection": "Inbox를 입력 대기/검토 중심으로, Raw Sources를 처리 완료 원본 archive로 재정의",
      "platformOrContext": "llm-wiki CLI/Web UI/Obsidian vault 구조",
      "successShape": "세 입력 유형별 ingest 동작, 성공/실패/review 이동 위치, chunk 처리 원칙이 명확함"
    },
    {
      "stage": 3,
      "name": "답을 찾는 과정은 뭔가",
      "score": 2,
      "status": "충분",
      "summary": "핵심 발견: parser는 chunks를 만들지만 현재 extraction은 parsed.chunks가 아니라 parsed.text truncate를 사용한다. 따라서 Inbox-first 재정비와 함께 chunked extraction map-reduce가 필요하다.",
      "discoveryTasks": [
        "Inbox 하위 폴더와 입력 유형별 진입점 결정",
        "성공한 원본을 Raw Sources archive로 move하는 정책 반영",
        "Review/Failed 위치를 Inbox 하위로 통합",
        "기존 Raw Sources 직접 ingest와 새 Inbox ingest의 관계 결정",
        "parsed.chunks 기반 chunked extraction map-reduce 설계 필요성 기록",
        "source_id와 archived raw path 연결 방식 검토"
      ],
      "functionalQuestions": [
        "Inbox 파일은 ingest 성공 시 Raw archive로 move",
        "실패 시 원본은 Inbox에 남기고, 실패 리포트/상태는 Inbox/_Failed에 남기는 방향",
        "Review 후보는 Inbox/_Review로 통합",
        "전체적인 흐름 재정비를 MVP 범위에 포함",
        "테스트를 위해 기존 wiki 자료는 삭제하고 기존 Raw 자료를 Inbox로 돌려 테스트 데이터로 사용"
      ],
      "uxQuestions": [
        "Web UI에서 Files/Markdown/Text 입력을 분리해 보여줄지",
        "Inbox 상태: 대기/처리중/검토/실패를 어디에서 확인할지",
        "Planning Stage 4에서 UI 흐름 검토 필요"
      ],
      "dataQuestions": [
        "source_id와 Raw archive path 연결",
        "chunk metadata는 파일 저장이 아니라 DB/runtime 처리 단위",
        "Inbox item status를 DB에 둘지 파일 frontmatter에 둘지",
        "테스트/전환 시 기존 wiki pages 삭제 범위와 Raw->Inbox 되돌림 절차"
      ],
      "technicalQuestions": [
        "parsed.chunks를 chunk별 extraction에 사용",
        "chunk summaries/candidates aggregate 후 기존 2-pass resolution에 연결",
        "LLM context overflow 시 chunked extraction fallback",
        "기존 Raw Sources 자료는 테스트용으로 Inbox로 이동 후 재처리"
      ],
      "constraints": [
        "원본 raw는 분할 저장하지 않음",
        "chunk는 처리 내부 단위",
        "성공한 Inbox 원본은 Raw Sources archive로 이동",
        "실패한 원본은 Inbox에 남겨 다시 처리 가능해야 함",
        "Wiki에는 검증/승인된 결과만 저장",
        "잘못된 merge보다 review/new가 안전",
        "테스트 전환에서는 기존 wiki 자료를 삭제하고 Inbox 기반 재처리로 검증"
      ],
      "priorities": [
        "데이터 손실 방지",
        "큰 문서 context overflow 해결",
        "사용자가 실패/검토 상태를 이해하기 쉽게 만들기",
        "Raw Sources를 사용자 입력점이 아닌 archive로 재정의",
        "테스트 가능한 end-to-end flow 확보"
      ]
    },
    {
      "stage": 4,
      "name": "구현·구체화 범위는 정했나",
      "score": 2,
      "status": "충분",
      "summary": "포함 범위는 전체 흐름 재정비로 잡혔다. reset은 반복 기능이 아니라 일회성 테스트 초기화(qmd/Obsidian 값 삭제 후 시작)로 정리되어 별도 명령 구현은 제외한다. 실패 원본은 Inbox/_Failed로, 리뷰 대상 원본/후보는 Inbox/_Review로 이동한다. Review는 유사도 기반 편입 선택지와 별도 태깅 입력 폼을 제공하는 검토 작업대가 된다. 실패 로그는 저장하되 오류 확인/처리 후 삭제한다.",
      "scopeIncluded": [
        "Inbox-first ingest 정보구조",
        "3가지 입력 유형: 문서파일, Markdown 스크랩, 붙여넣기 텍스트",
        "성공한 원본을 Raw Sources archive로 이동",
        "실패한 원본은 Inbox에 남겨 재처리 가능하게 유지",
        "Review 후보를 Inbox/_Review로 통합",
        "Failed 상태/리포트를 Inbox/_Failed로 분리",
        "chunked extraction을 처리 내부 단위로 사용",
        "기존 Raw Sources 자료를 테스트용으로 Inbox에 되돌려 재처리",
        "테스트를 위해 기존 qmd/Obsidian 값을 일회성으로 초기화 후 재생성 검증",
        "CLI와 Web UI 전체 흐름 재정비"
      ],
      "scopeExcluded": [
        "원본 raw 파일을 chunk별로 물리 분할 저장",
        "검증되지 않은 LLM 결과를 바로 Wiki canonical page로 확정",
        "Raw Sources를 사용자 입력점으로 계속 유지하는 구조",
        "HTML mockup/Lavish 리뷰는 Ideation에서 하지 않음"
      ],
      "missingCandidates": [
        "실패 원본은 Inbox/_Failed, 리뷰 대상 원본/후보는 Inbox/_Review로 이동",
        "Inbox/_Failed에는 원인 파악용 로그/리포트를 함께 저장",
        "_Failed 로그는 저장 후 오류 확인/처리되면 삭제",
        "Inbox/_Processing 임시 이동/lock 파일 정책",
        "DB source status와 파일 위치 상태 동기화 방식",
        "실패 후 재시도 UX",
        "Wiki 반영과 Raw archive 이동 사이 중간 장애 롤백 정책",
        "중복 입력/파일명 충돌/동시 ingest 잠금 정책",
        "_Review는 기존 Wiki 유사 항목 편입 후보를 제시하고, 편입 대상이 없으면 별도 태깅/분류 입력 폼을 제공",
        "_Review 원본은 공간 낭비 방지를 위해 복사하지 않고 이동 중심으로 관리"
      ],
      "subagentReviewNotes": [
        "MiniMax3 cross-check: move 경계, 상태 전이, review/failed 저장물, 원자성/복구, 중복/충돌/동시성 정책이 미확정이므로 Stage 4는 1점 권장",
        "reset은 제품 기능이 아니라 현재 테스트 전 일회성 초기화로 정리됨",
        "상태 전이표와 원본/보고서/후보/Wiki/DB 저장 위치를 Planning 전에 확정해야 함"
      ],
      "userReconfirmedItems": [
        "성공한 Inbox 원본은 Raw Sources archive로 이동",
        "Review 후보는 Inbox/_Review로 통합",
        "실패한 원본은 Inbox/_Failed로 이동하고 원인 파악 로그를 남기되 확인 후 삭제",
        "리뷰 원본은 공간 낭비 없이 Inbox/_Review로 이동",
        "Review UI는 유사도 기반 편입 선택지와 별도 태깅 입력 폼을 제공",
        "CLI/Web UI 포함 전체 흐름 재정비",
        "테스트 전 qmd/Obsidian 값은 일회성 초기화하고 Inbox 기반 재처리",
        "reset용 별도 명령 구현은 필요 없음"
      ]
    },
    {
      "stage": 5,
      "name": "최종 모호성 점검",
      "score": 1,
      "status": "부분충분",
      "summary": "핵심 방향과 범위는 정리됐고 사용자가 이 상태로 Planning 전환을 승인했다. 남은 세부 모호성은 Planning에서 상세화한다.",
      "finalSummary": "Inbox를 입력 지점으로 삼고, 성공한 원본은 Raw Sources archive로 이동한다. 실패 원본은 Inbox/_Failed로 이동하고 원인 로그를 남기며, 오류 확인/처리 후 로그를 삭제한다. Review 대상은 Inbox/_Review로 이동하고, UI는 기존 Wiki 유사 항목 편입 선택지와 별도 태깅 입력 폼을 제공한다. 큰 문서는 parsed.chunks 기반 chunked extraction map-reduce로 처리한다. CLI/Web UI 포함 전체 흐름을 재정비한다.",
      "confirmedDirection": "Inbox-first 구조, Raw Sources archive 전환, _Failed/_Review 이동, Review 작업대 UI, chunked extraction 필요성이 확인됨",
      "remainingAmbiguities": [
        "테스트 전환에서 Raw->Inbox는 실제 move인지 안전한 copy인지",
        "Processing lock/status 방식은 Planning에서 설계 필요",
        "UI 흐름 검토는 Planning Stage 4에서 mockup/Lavish 필요",
        "Raw archive 이동 실패 등 중간 장애 복구 정책은 Planning에서 상세화 필요"
      ],
      "userApprovalStatus": "approved",
      "planningHandoffBrief": "Inbox-first ingest로 전체 흐름을 재정비한다. Inbox가 입력 지점이고 성공 원본은 Raw Sources archive로 이동한다. 실패 원본은 Inbox/_Failed로 이동하고 로그/리포트를 남긴 뒤 처리 후 삭제한다. Review 대상은 Inbox/_Review로 이동하고 유사 Wiki 편입 선택지와 별도 태깅 입력 폼을 제공한다. 큰 문서는 parsed.chunks 기반 chunked extraction map-reduce로 처리한다. CLI/Web UI 포함 전체 흐름 재정비가 범위다. Processing lock/status와 중간 장애 복구는 Planning에서 상세 설계한다."
    }
  ],
  "regressionLog": [
    "Stage 2 목표가 '세 입력 유형 원칙'에서 '전체적인 흐름 재정비'로 넓어졌으므로 Stage 3~5를 재점검했다.",
    "Stage 4 범위가 CLI/Web UI 포함 전체 재정비로 확장되어 Stage 5는 최종 모호성 점검 전으로 유지한다.",
    "MiniMax3 cross-check 결과 reset/move 경계와 상태 전이가 미확정이라 Stage 4를 2점에서 1점으로 낮췄다.",
    "사용자가 reset은 반복 기능이 아니라 qmd/Obsidian 값을 지우고 시작하는 일회성 테스트 초기화라고 정정했다.",
    "사용자가 Review 처리 방식과 Failed 로그 정책을 확정해 Stage 4를 2점으로 복구하고 Stage 5를 부분충분으로 올렸다."
  ],
  "lastUserAnswer": "이 상태로 planning으로 가자.",
  "nextQuestions": [
    "02 Planning 시작"
  ],
  "pendingAmbiguities": [
    "Processing lock/status 방식은 Planning 상세화",
    "중간 장애 복구는 Planning 상세화"
  ]
}
```
