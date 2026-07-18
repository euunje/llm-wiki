from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_wiki.config import DEFAULT_SETTINGS, load_settings, save_settings
from llm_wiki.db import SchemaResult, ensure_database
from llm_wiki.workspace import WorkspacePaths, required_directories


RAW_README = "# Raw source area\n\nThis vault folder is a human-facing index area for raw materials.\n"
PLACEHOLDER_TEMPLATE = "# Placeholder\n\nPhase 1 placeholder.\n"


def ensure_workspace(paths: WorkspacePaths) -> dict[str, Any]:
    created_dirs: list[str] = []
    for directory in required_directories(paths):
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        if not existed:
            created_dirs.append(str(directory.relative_to(paths.root)))
    created_files: list[str] = []
    created_files.extend(_ensure_placeholder_files(paths))
    schema = ensure_database(paths.db)
    if not paths.settings_file.exists():
        save_settings(paths.settings_file, DEFAULT_SETTINGS)
        created_files.append(str(paths.settings_file.relative_to(paths.root)))
    else:
        load_settings(paths.settings_file)
    return {
        "created_directories": created_dirs,
        "created_files": created_files,
        "schema": schema_to_dict(schema, paths.root),
    }


def _ensure_file(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _ensure_placeholder_files(paths: WorkspacePaths) -> list[str]:
    created: list[str] = []
    mapping = {
        paths.raws / "README.md": RAW_README,
        paths.templates / "README.md": PLACEHOLDER_TEMPLATE,
        paths.prompts / "README.md": PLACEHOLDER_TEMPLATE,
        paths.ontology / "README.md": PLACEHOLDER_TEMPLATE,
    }
    for file_path, content in mapping.items():
        if _ensure_file(file_path, content):
            created.append(str(file_path.relative_to(paths.root)))
    return created


def schema_to_dict(schema: SchemaResult, root: Path) -> dict[str, Any]:
    return {
        "db_path": str(schema.db_path.relative_to(root)),
        "created": schema.created,
        "migrations_applied": schema.migrations_applied,
        "fts5_enabled": schema.fts5_enabled,
        "fts5_message": schema.fts5_message,
    }
