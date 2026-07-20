"""Test package for Phase 1 LLM Wiki Local CLI foundation.

Run via:

    PYTHONPATH=src python3 -m pytest tests -q

This package builds a fresh workspace under ``tmp_path`` for each test and only
references files inside the temporary directory or the repository's ``samples/``
fixtures. The package never touches ``data/`` or ``vault/`` at the repo root and
never reads, writes, or copies ``.env`` secret values.
"""
