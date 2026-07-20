# LLM Wiki Local

현재 기준은 Phase 3 normal-operation 웹 계약입니다. 구계약/하위호환 기대는 폐기되었습니다.

## 현재 웹 계약 요약

- `setup_complete`는 설정값 존재만으로 켜지지 않습니다. **실제 LLM 연결 테스트(chat + embedding) 통과**가 필요합니다.
- setup이 끝나기 전까지 Onboarding이 게이트입니다. 보호 페이지는 미완료 시 `/onboarding`으로 리다이렉트됩니다.
- Onboarding vault 폴더 브라우저는 **workspace root가 아니라 실제 HOME(`Path.home()`)에서 시작**합니다. 따라서 `~/vault` 같은 폴더를 직접 선택할 수 있습니다.
- Onboarding 폴더 브라우저는 **HOME 밖으로 올라갈 수 없고**, `..` 경로 이동, HOME 밖 절대경로, 숨김(`.`) 경로, symlink 경로를 거부합니다. 목록에서도 symlink는 숨깁니다.
- 기존 vault 매핑은 `~/vault` 또는 HOME 하위의 안전한 절대경로를 받아 저장할 수 있지만, **runtime/data/db/cache/artifacts 경로를 사람용 vault 아래로 강제로 옮기지 않습니다**. 현재 workspace runtime 경로는 그대로 유지됩니다.
- Prompt Confirm는 **최신 passed `prompt_test_result` artifact**가 있어야 하며, 사용자 입력 label/note로 우회할 수 없습니다.
- Mapping Apply는 **preview-bound confirm**입니다. `preview_decision_id` 없이 직접 apply 하면 거부됩니다.
- Inbox processing은 현재 **동기(synchronous)** 처리이며, 응답의 현재 계약 필드는 `execution_mode`와 `acceptance_status`입니다.
  - `failed` / `blocked` / `degraded` 상태를 숨기지 않고 그대로 보고합니다.
  - `queued_count`가 남아 있더라도 이는 legacy/deprecated 호환 필드입니다.
- Logout은 기본 top navigation 항목이 아닙니다. 승인 UX 기준으로 `Settings > Auth`의 임시 액션에 위치합니다.

## Environment-backed LLM defaults

- `.env.sample` documents the reusable keys: `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, `LLM_WIKI_EMBEDDING_MODEL`, and `LLM_WIKI_API_KEY`.
- When `vault/90_Settings/settings.yaml` leaves the LLM endpoint or per-model `model_name` / `endpoint` blank, runtime may resolve those values from the environment.
- Non-empty YAML settings override environment values.

## Run from source

```bash
PYTHONPATH=src python3 -m llm_wiki.cli --help
```
