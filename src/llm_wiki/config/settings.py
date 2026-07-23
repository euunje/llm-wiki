from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from llm_wiki.common import ensure_parent, parse_scalar

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


class SettingsError(RuntimeError):
    pass


DEFAULT_SETTINGS: dict[str, Any] = {
    "paths": {
        "vault": "vault",
        "data": "data",
        "db": "data/wiki.sqlite",
        "raw": "data/raw",
        "normalized": "data/normalized",
        "artifacts": "data/artifacts",
        "exports": "data/exports",
        "cache": "data/cache",
        "settings": "settings.yaml",
    },
    "workspace": {
        "human_vault": "vault",
        "system_data": "data",
    },
    "embedding": {
        "backend": "fastembed",
        "model_root": "data/models/embeddings",
        "default_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "fallback_model": "fallback-hash-v1",
        # fastembed_timeout_seconds: integer >= 1. Values <= 0 are clamped to 1 at runtime.
        # Minimum bound: 1 second. Maximum is unlimited but very large values are untested.
        "fastembed_timeout_seconds": 30,
    },
    "chunking": {
        "max_chars": 1000,
        "overlap_chars": 200,
    },
    "inbox": {
        "paths": {
            "files": "vault/00_Inbox/files",
            "memo": "vault/00_Inbox/memo",
            "text": "vault/00_Inbox/text",
        },
    },
    "llm": {
        "endpoint": "",
        "api_key_env": "LLM_WIKI_API_KEY",
        "default_chat_model": "",
        "default_embedding_model": "embedding_default",
        "timeout_seconds": 300,
        "models": {
            "chat_default": {
                "id": "chat_default",
                "provider": "generic_openai_compatible",
                "capability": "chat",
                "endpoint": "",
                "api_key_env": "LLM_WIKI_API_KEY",
                "model_name": "",
                "request_format": "openai_chat",
            },
            "embedding_default": {
                "id": "embedding_default",
                "provider": "local_embedding_folder",
                "capability": "embedding",
                "model_name": "",
                "request_format": "local_embedding_folder",
            },
        },
        "routing": {
            "extract_claims": "chat_default",
            "ask": "chat_default",
        },
    },
    "env": {
        "file": ".env",
    },
    "web": {
        "host": "",
        "port": None,
        "session_cookie_name": "llm_wiki_web_session",
        "session_ttl_seconds": 43200,
        "admin_password_env": "LLM_WIKI_WEB_ADMIN_PASSWORD",
    },
    "sync": {
        "default_apply": False,
    },
}


def _fallback_dump(data: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    lines: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_fallback_dump(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_scalar_to_yaml(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_fallback_dump(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_scalar_to_yaml(item)}")
    return lines


def _scalar_to_yaml(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(ch in text for ch in [":", "#", "\n"]) or text.strip() != text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _fallback_load(text: str) -> Any:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if line.endswith(":"):
            key = line[:-1].strip()
            new_obj: dict[str, Any] = {}
            if not isinstance(container, dict):
                raise SettingsError("Fallback YAML parser supports dict-based settings only")
            container[key] = new_obj
            stack.append((indent, new_obj))
            continue
        if line.startswith("- ") or line == "-":
            raise SettingsError("Fallback YAML parser does not support list settings in this file")
        if ":" not in line or not isinstance(container, dict):
            raise SettingsError("Invalid settings YAML format")
        key, value = line.split(":", 1)
        container[key.strip()] = parse_scalar(value.strip())
    return root


def _env_or_yaml(env_name: str, settings_value: Any) -> str:
    if isinstance(settings_value, str) and settings_value.strip():
        return settings_value
    if settings_value not in (None, ""):
        return str(settings_value)
    return os.environ.get(env_name, "")


def _resolve_llm_settings(data: dict[str, Any]) -> dict[str, Any]:
    resolved = copy.deepcopy(data)
    llm = resolved.get("llm")
    if not isinstance(llm, dict):
        return resolved

    llm["endpoint"] = _env_or_yaml("LLM_WIKI_LLM_ENDPOINT", llm.get("endpoint"))
    llm["default_chat_model"] = _env_or_yaml("LLM_WIKI_CHAT_MODEL", llm.get("default_chat_model"))

    models = llm.get("models")
    if not isinstance(models, dict):
        return resolved

    for model_id, raw_model in models.items():
        if not isinstance(raw_model, dict):
            continue
        model = raw_model
        model["id"] = model.get("id") or model_id
        capability = model.get("capability")
        if capability == "chat":
            model["endpoint"] = _env_or_yaml("LLM_WIKI_LLM_ENDPOINT", model.get("endpoint"))
            model["model_name"] = _env_or_yaml("LLM_WIKI_CHAT_MODEL", model.get("model_name"))
    return resolved


def load_settings(path: Path, *, resolve_env: bool = True) -> dict[str, Any]:
    if not path.exists():
        raise SettingsError(f"Settings file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise SettingsError("Settings file must contain a mapping at the top level")
    else:
        loaded = _fallback_load(text)
    if not isinstance(loaded, dict):
        raise SettingsError("Settings file must contain a mapping at the top level")
    if not resolve_env:
        return loaded
    return _resolve_llm_settings(loaded)


def save_settings(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    if yaml is not None:
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    else:
        text = "\n".join(_fallback_dump(data)) + "\n"
    path.write_text(text, encoding="utf-8")


def set_setting(settings: dict[str, Any], dotted_key: str, raw_value: str) -> tuple[dict[str, Any], Any, Any]:
    new_settings = copy.deepcopy(settings)
    keys = dotted_key.split(".")
    cursor: Any = new_settings
    original_cursor: Any = settings
    for key in keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            raise SettingsError(f"Unknown settings key: {dotted_key}")
        cursor = cursor[key]
        original_cursor = original_cursor[key]
    final_key = keys[-1]
    if final_key not in cursor:
        raise SettingsError(f"Unknown settings key: {dotted_key}")
    old_value = original_cursor[final_key]
    new_value = parse_scalar(raw_value)
    cursor[final_key] = new_value
    return new_settings, old_value, new_value
