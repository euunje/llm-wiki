"""OpenAI-compatible Phase 2 chat JSON runner with safe parsing."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from llm_wiki.llm.models import _request_endpoint, _resolve_model
from llm_wiki.workspace import WorkspacePaths


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from plain text or fenced Markdown."""
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return _loads_json_object(fence.group(1))
    if stripped.startswith("{"):
        return _loads_json_object(stripped)
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
                return _loads_json_object(stripped[start:index + 1])
    raise ValueError("LLM response JSON object is not balanced")


def _loads_json_object(raw: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        loaded = json.loads(cleaned)
    if not isinstance(loaded, dict):
        raise ValueError("LLM JSON payload is not an object")
    return loaded


def call_json_task(
    workspace: WorkspacePaths,
    *,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1600,
) -> dict[str, Any]:
    model = _resolve_model(workspace, model_id)
    endpoint = str(model.get("endpoint") or "")
    model_name = str(model.get("model_name") or "")
    if not endpoint or not model_name:
        raise ValueError("model endpoint or model_name not configured")
    if model.get("capability") != "chat" or model.get("request_format") != "openai_chat":
        raise ValueError("Phase 2 JSON task requires openai_chat model capability")
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(str(model.get("api_key_env") or ""))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    raw = _post_first_successful(endpoint, model.get("request_format"), body, headers, int(model.get("timeout_seconds") or 20))
    parsed_response = json.loads(raw)
    if isinstance(parsed_response, dict) and parsed_response.get("error"):
        raise ValueError(f"LLM response error: {parsed_response.get('error')}")
    content = _extract_text_content(parsed_response)
    if not isinstance(content, str):
        raise ValueError("LLM response has no text content")
    return {
        "content": content,
        "parsed_json": extract_json_object(content),
        "http_response_size_bytes": len(raw.encode("utf-8")),
        "api_key_present": bool(api_key),
    }


def _candidate_endpoints(endpoint: str, request_format: str | None) -> list[str]:
    primary = _request_endpoint(endpoint, request_format)
    candidates = [primary]
    normalized = endpoint.rstrip("/")
    if request_format == "openai_chat":
        for suffix in ("/v1/chat/completions", "/chat/completions"):
            candidate = normalized + suffix
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


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
