# Web UI Stack — Phase 3

## 결정

Phase 3 Web UI는 다음 stack으로 완성한다.

| 영역 | 기술 |
|---|---|
| Backend/API | FastAPI |
| Server | uvicorn |
| Template | Jinja2 |
| Forms | python-multipart |
| Schema validation | pydantic |
| Settings | PyYAML |
| Env | python-dotenv |
| Frontend | server-rendered HTML + Vanilla JavaScript ES modules |
| Styling | plain CSS |
| Graph popup | inline SVG + Vanilla JS |
| Auth | `.env` 관리자 비밀번호 + stdlib hmac signed session cookie |

## 제외

- React/Vite/Next.js
- Tailwind build pipeline
- 별도 graph library 필수 의존
- OAuth/passlib 등 복잡한 auth framework
- 다중 사용자 권한

## Dependency 승인 범위

Build agent는 아래 package 추가를 승인된 것으로 본다.

- `fastapi`
- `uvicorn`
- `jinja2`
- `python-multipart`
- `pydantic`
- `PyYAML`
- `python-dotenv`

이 목록 외 dependency가 필요하면 구현을 중단하고 사용자 승인을 요청한다.

## 구현 방향

- CLI와 Web은 같은 service/repository 계층을 공유한다.
- Web은 DB/job/artifact/read model을 통해 상태를 보여준다.
- Review interaction은 필요한 API endpoint + Vanilla JS로 구현한다.
- Graph popup은 1-hop relation 데이터를 받아 SVG로 렌더링한다.
