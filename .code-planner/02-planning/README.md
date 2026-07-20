# LLM Wiki Local — 02 Planning

## 현재 단계

- Stage 1 기술 논의: 완료
- Stage 2 기술 확정 및 문서화: 완료
- Stage 3 Phase 설계: 완료
- Stage 4 기능 계약 및 목업 제시: 완료
- Stage 5 Phase fix 및 문서화: 완료
- Stage 6 Validation plan: 완료
- Stage 7 Crosscheck: 완료
- Stage 8 Build handoff: 완료

## 입력 artifact

- 승인된 Ideation: `.code-planner/01-ideation-approved.json`
- Vault living note: `/home/eunjae/vault/60. Projects/code-planner/01_Idation/llm-wiki-local-ideation.md`

## 확정된 기술 방향

- 실행 환경: 로컬 Linux 단일 사용자 기준
- 배포: 1차에서는 제외, 3차 Web UI에서 로컬 서버 중심 고려
- 구현 언어: Python
- 저장소: Obsidian Vault + SQLite
- CLI: 1차 핵심 구현 대상
- Web UI: 3차 구현 대상, API/Web 연계를 고려한 구조
- Embedding: `fastembed` + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- LLM 런타임: 열린 설정 + sample env 제공
- 동기화: 1차 수동 `wiki sync`
- Git remote 후보: `git@github.com:euunje/llm-wiki-local.git`
- Git 운영: 단일 브랜치 + phase별 commit

## Planning 시작 요약

- 1차 목표: CLI 기능 구현
- 2차 목표: LLM wiki 프롬프트 품질, WikiPage/page 처리, PDF/Office/HTML/URL 변환
- 3차 목표: Web UI

## Planning에서 반드시 다룰 항목

1. 기술 방향 확정
2. CLI phase 분해와 검증 목표
3. Web Review UX 목업 생성 및 검토
4. LLM schema 세부 JSON/validator 설계
5. Git/commit 운영 방식
