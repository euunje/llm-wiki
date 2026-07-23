"""OpenAI-compatible Phase 2 chat JSON runner with safe parsing."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from llm_wiki.config import load_settings
from llm_wiki.llm.models import _openai_base_url, _request_endpoint, _resolve_model
from llm_wiki.workspace import WorkspacePaths


class LLMJsonParseError(ValueError):
    def __init__(self, message: str, *, content: str):
        self.content = content
        super().__init__(message)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from plain text or fenced Markdown."""
    return extract_json_object_with_repair(text)["parsed_json"]


def extract_json_object_with_repair(text: str) -> dict[str, Any]:
    """Extract and parse a JSON object, applying conservative local repairs.

    Local LLMs often return semantically correct JSON-shaped text with small
    syntax defects: fenced blocks, trailing commas, a missing comma between
    properties, or unescaped quotes inside natural-language value strings.  The
    parser repairs only those narrow cases and still lets schema validation
    decide whether the decoded object is acceptable.
    """
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        parsed, repaired = _loads_json_object(fence.group(1))
        return {"parsed_json": parsed, "json_repair_applied": repaired}
    if stripped.startswith("{"):
        parsed, repaired = _loads_json_object(stripped)
        return {"parsed_json": parsed, "json_repair_applied": repaired}
    start = stripped.find("{")
    if start < 0:
        raise ValueError("LLM response does not contain a JSON object")
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(stripped[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                parsed, repaired = _loads_json_object(stripped[start:index + 1])
                return {"parsed_json": parsed, "json_repair_applied": repaired}
    raise ValueError("LLM response JSON object is not balanced")


def _loads_json_object(raw: str) -> tuple[dict[str, Any], bool]:
    try:
        loaded = json.loads(raw)
        repaired = False
    except json.JSONDecodeError:
        cleaned = _repair_jsonish_object(raw)
        loaded = json.loads(cleaned)
        repaired = cleaned != raw
    if not isinstance(loaded, dict):
        raise ValueError("LLM JSON payload is not an object")
    return loaded, repaired


def _repair_jsonish_object(raw: str) -> str:
    """Best-effort repair for common local-LLM JSON syntax defects."""
    cleaned = raw.strip().replace("“", '"').replace("”", '"')
    # Trailing commas before object/array close.
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    # Missing comma between a completed value and the next property key.
    cleaned = re.sub(
        r'("|\]|\}|\d|true|false|null)\s*\n\s*("[A-Za-z0-9_\-]+"\s*:)',
        r"\1,\n\2",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _escape_unescaped_value_quotes(cleaned)


def _escape_unescaped_value_quotes(text: str) -> str:
    """Escape stray quotes that appear inside JSON string values.

    This intentionally avoids broad transformations.  A quote inside a value
    string is considered a closing quote only when the next non-space character
    is a structural delimiter (comma, object close, or array close).  Quotes
    before ordinary text or a colon are treated as literal content and escaped.
    Key strings still close before a colon.
    """
    out: list[str] = []
    in_string = False
    escape = False
    string_kind: str | None = None

    def prev_nonspace() -> str:
        for item in reversed(out):
            if not item.isspace():
                return item
        return ""

    def next_nonspace(index: int) -> str:
        j = index + 1
        while j < len(text) and text[j].isspace():
            j += 1
        return text[j] if j < len(text) else ""

    def starts_key(index: int) -> bool:
        prev = prev_nonspace()
        if prev not in {"{", ","}:
            return False
        j = index + 1
        escaped = False
        while j < len(text):
            ch = text[j]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                k = j + 1
                while k < len(text) and text[k].isspace():
                    k += 1
                return k < len(text) and text[k] == ":"
            j += 1
        return False

    for index, char in enumerate(text):
        if escape:
            out.append(char)
            escape = False
            continue
        if char == "\\":
            out.append(char)
            if in_string:
                escape = True
            continue
        if char != '"':
            out.append(char)
            continue

        if not in_string:
            in_string = True
            string_kind = "key" if starts_key(index) else "value"
            out.append(char)
            continue

        nxt = next_nonspace(index)
        if string_kind == "key":
            if nxt == ":":
                in_string = False
                string_kind = None
                out.append(char)
            else:
                out.append('\\"')
            continue

        if nxt in {",", "}", "]"}:
            in_string = False
            string_kind = None
            out.append(char)
        else:
            out.append('\\"')
    return "".join(out)


def call_json_task(
    workspace: WorkspacePaths,
    *,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    model = _resolve_model(workspace, model_id)
    endpoint = str(model.get("endpoint") or "")
    model_name = str(model.get("model_name") or "")
    if not endpoint or not model_name:
        raise ValueError("model endpoint or model_name not configured")
    if model.get("capability") != "chat" or model.get("request_format") != "openai_chat":
        raise ValueError("Phase 2 JSON task requires openai_chat model capability")
    advanced = _llm_advanced_options(workspace)
    request_temperature = advanced.get("temperature", 0)
    request_max_tokens = max_tokens if max_tokens is not None else advanced.get("max_tokens")
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": request_temperature,
    }
    if request_max_tokens is not None:
        body["max_tokens"] = request_max_tokens
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(str(model.get("api_key_env") or ""))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    raw = _post_first_successful(endpoint, model.get("request_format"), body, headers, int(model.get("timeout_seconds") or 300))
    parsed_response = json.loads(raw)
    if isinstance(parsed_response, dict) and parsed_response.get("error"):
        raise ValueError(f"LLM response error: {parsed_response.get('error')}")
    content = _extract_text_content(parsed_response)
    if not isinstance(content, str):
        raise ValueError("LLM response has no text content")
    try:
        parsed_payload = extract_json_object_with_repair(content)
    except Exception as exc:
        raise LLMJsonParseError(str(exc), content=content) from exc
    return {
        "content": content,
        "parsed_json": parsed_payload["parsed_json"],
        "json_repair_applied": parsed_payload["json_repair_applied"],
        "http_response_size_bytes": len(raw.encode("utf-8")),
        "api_key_present": bool(api_key),
    }


def _llm_advanced_options(workspace: WorkspacePaths) -> dict[str, Any]:
    settings = load_settings(workspace.settings_file, resolve_env=False)
    advanced = (settings.get("llm") or {}).get("advanced") or {}
    options: dict[str, Any] = {}
    temperature = advanced.get("temperature")
    if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
        options["temperature"] = float(temperature)
    max_tokens = advanced.get("max_tokens")
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool) and max_tokens > 0:
        options["max_tokens"] = max_tokens
    return options


def _candidate_endpoints(endpoint: str, request_format: str | None) -> list[str]:
    normalized = endpoint.rstrip("/")
    primary = _request_endpoint(endpoint, request_format)
    candidates: list[str] = []
    if request_format == "openai_chat":
        if normalized.endswith("/v1/chat/completions") or normalized.endswith("/chat/completions"):
            candidates.append(primary)
        else:
            base = _openai_base_url(endpoint)
            candidates.append(f"{base}/chat/completions")
            candidates.append(f"{normalized}/chat/completions")
    else:
        candidates.append(primary)
    return list(dict.fromkeys(candidates))


def _post_first_successful(endpoint: str, request_format: str | None, body: dict[str, Any], headers: dict[str, str], timeout: int) -> str:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for candidate_endpoint in _candidate_endpoints(endpoint, request_format):
        request = urllib.request.Request(candidate_endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return raw
            if isinstance(parsed, dict) and parsed.get("error") and "Unexpected endpoint" in str(parsed.get("error")):
                last_error = ValueError(str(parsed.get("error")))
                continue
            return raw
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            last_error = RuntimeError(f"HTTP Error {exc.code}: {exc.reason}; response body: {detail}")
            continue
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise ValueError("No candidate endpoint attempted")


def _extract_text_content(parsed_response: Any) -> str | None:
    if not isinstance(parsed_response, dict):
        return None
    choices = parsed_response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    for key in ("content", "response", "text", "output_text"):
        if isinstance(parsed_response.get(key), str):
            return parsed_response[key]
    return None
