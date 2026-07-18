# LLM Wiki Local

Phase 1 CLI foundation.

## Environment-backed LLM defaults

- `.env.sample` documents the reusable Phase 1 keys: `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, `LLM_WIKI_EMBEDDING_MODEL`, and `LLM_WIKI_API_KEY`.
- When `vault/90_Settings/settings.yaml` leaves the LLM endpoint or per-model `model_name` / `endpoint` blank, the CLI resolves those values from the environment at runtime.
- YAML settings override environment values when the YAML field is non-empty.

Project note: `docs/01_cli_features.md` and `docs/03_schema_and_ontology.md` are project-wide reference docs that predate the Phase 1 implementation work.

## Run from source

```bash
PYTHONPATH=src python3 -m llm_wiki.cli --help
```
