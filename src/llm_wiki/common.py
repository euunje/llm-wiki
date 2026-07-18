from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_FRAGMENTS = ("secret", "token", "password", "api_key", "apikey", "key")

# Keys whose name (case-insensitive) must always be redacted
AUTHORIZATION_KEYS = frozenset({"authorization", "proxy-authorization", "x-api-key", "api-key"})


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in AUTHORIZATION_KEYS:
        return True
    return any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS)


def mask_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"{text[:2]}***{text[-2:]}"


def redact_bearer_tokens(text: str) -> str:
    """Redact 'Bearer <token>' fragments from a string, leaving the structure intact."""
    import re
    return re.sub(r"Bearer\s+[^\s,}\]]+", "Bearer ***", text)


def mask_sensitive(data: Any, parent_key: str = "") -> Any:
    if isinstance(data, dict):
        return {
            key: mask_sensitive(value, key)
            if not is_sensitive_key(key)
            else mask_value(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive(item, parent_key) for item in data]
    if parent_key and is_sensitive_key(parent_key):
        return mask_value(data)
    # Redact Bearer tokens even in non-sensitive fields
    if isinstance(data, str) and "Bearer " in data:
        return redact_bearer_tokens(data)
    return data


def parse_scalar(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if raw.startswith("0") and raw != "0" and not raw.startswith("0."):
            raise ValueError
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def relative_to(base: Path, target: Path) -> str:
    return os.fspath(target.relative_to(base))
