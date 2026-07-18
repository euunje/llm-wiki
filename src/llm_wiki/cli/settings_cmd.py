from __future__ import annotations

import argparse
from typing import Any

from llm_wiki.common import mask_sensitive
from llm_wiki.config import SettingsError, load_settings, save_settings, set_setting
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import resolve_workspace


def _get_dotted(data: dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            raise SettingsError(f"Unknown settings key: {dotted_key}")
        current = current[key]
    return current


def run_settings_get(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    settings = load_settings(workspace.settings_file)
    value = settings if not args.key else _get_dotted(settings, args.key)
    return 0, {
        "status": "ok",
        "workspace": str(workspace.root),
        "settings_path": str(workspace.settings_file),
        "key": args.key,
        "value": mask_sensitive(value, args.key or ""),
        "message": "Settings loaded",
    }


def run_settings_set(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    settings = load_settings(workspace.settings_file, resolve_env=False)
    updated, old_value, new_value = set_setting(settings, args.key, args.value)
    save_settings(workspace.settings_file, updated)
    artifact = record_artifact(
        workspace,
        artifact_type="settings_change",
        task_type="settings",
        payload={
            "status": "ok",
            "key": args.key,
            "old_value": mask_sensitive(old_value, args.key),
            "new_value": mask_sensitive(new_value, args.key),
        },
        target_type="settings",
        target_id="global",
    )
    return 0, {
        "status": "ok",
        "workspace": str(workspace.root),
        "settings_path": str(workspace.settings_file),
        "key": args.key,
        "old_value": mask_sensitive(old_value, args.key),
        "new_value": mask_sensitive(new_value, args.key),
        **artifact,
        "message": f"Updated {args.key}",
    }
