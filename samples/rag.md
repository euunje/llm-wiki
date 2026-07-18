# Retrieval-Augmented Generation Overview

Retrieval-Augmented Generation (RAG) combines a retrieval step with a language model.
A typical pipeline ingests documents, normalizes their text, then chunks them so the
retriever can embed each chunk into a vector space.

## Pipeline Stages

1. Ingest Markdown files from the inbox.
2. Normalize the text by stripping trailing whitespace and preserving Markdown.
3. Chunk the normalized text using a fixed character budget with overlap.
4. Embed each chunk into a vector; Phase 1 falls back to a deterministic hash-based
   vector when fastembed is not installed.

## Sample Notes

This file is used by the Phase 1 validation harness. It exists only to exercise the
ingest → normalize → chunk → embed pipeline. Extra padding is included below so that
the default chunking settings can produce more than one chunk if so desired.

LLM Wiki Local keeps the original raw file in `data/raw/`, the normalized text in
`data/normalized/`, embedding vectors in SQLite, and observable artifacts in
`data/artifacts/`. The CLI surface does not depend on a web UI and is safe to run in
test workspaces under `/tmp/opencode`.
