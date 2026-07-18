"""Shared pytest fixtures for Phase 1 test suite.

Every fixture here builds a workspace inside ``tmp_path`` provided by pytest
so no persistent state is created in the repository tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
SAMPLES_DIR = REPO_ROOT / "samples"


def _pythonpath() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    return str(SRC_ROOT) + (os.pathsep + existing if existing else "")


def _run_cli(*args: str, workspace: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath()
    return subprocess.run(
        [sys.executable, "-m", "llm_wiki.cli", *args, "--path", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(SRC_ROOT),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Return a path that ``wiki`` considers a fresh workspace root."""
    return tmp_path


@pytest.fixture
def repo_root() -> Path:
    """Repository root constant for tests that need access to ``samples/``."""
    return REPO_ROOT


@pytest.fixture
def samples_dir() -> Path:
    """Path to the curated sample Markdown fixtures."""
    return SAMPLES_DIR


@pytest.fixture
def cli_runner():
    """Helper that invokes the CLI in a subprocess with ``PYTHONPATH=src``."""

    def _runner(*args: str, workspace: Path) -> subprocess.CompletedProcess:
        return _run_cli(*args, workspace=workspace)

    return _runner
