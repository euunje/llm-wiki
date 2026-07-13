"""Ollama & OpenAI-compatible Unified HTTP Client.

Supports:
- Ollama local endpoint
- OpenAI (and OpenAI-compatible endpoints like LM Studio)
- Thinking mode toggle (Qwen3's /think, /no_think inline tags)
- JSON mode (format='json' / response_format)
- Streaming for real-time page drafting
"""

from __future__ import annotations

import os
import json
import re
import sys
from dataclasses import dataclass
from typing import Generator, Iterator
from pathlib import Path

import httpx

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"
DEFAULT_TIMEOUT = 300.0  # 5 minutes — thinking-mode extraction can be slow


class LLMError(Exception):
    """Raised when an LLM call fails in a user-recoverable way."""


class OllamaNotRunning(LLMError):
    """Ollama HTTP API is not reachable."""


class ModelNotFound(LLMError):
    """Requested model isn't pulled."""


@dataclass
class ChatMessage:
    role: str  # 'system' | 'user' | 'assistant'
    content: str


class OllamaClient:
    """Unified client supporting both Ollama and OpenAI-compatible APIs (like LM Studio)."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        provider: str | None = None,
        api_key: str | None = None,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        
        # Load provider and API keys from config if not passed
        self.provider = provider
        self.api_key = api_key
        
        if not self.provider:
            # Try to resolve from config
            try:
                from . import config as cfg
                root = cfg.find_wiki_root()
                if root:
                    paths = cfg.WikiPaths(root=root)
                    config = cfg.load_config(paths)
                    self.provider = config.get("llm", {}).get("provider", "ollama")
                    
                    # Read .env for API Key
                    from .webapp.routes.setup import read_dirs # dummy import check
                    env_file = os.environ.get("ENV_FILE_PATH")
                    env_path = Path(env_file) if env_file else paths.root / ".env"
                    if env_path.exists():
                        env_content = env_path.read_text(encoding="utf-8")
                        for line in env_content.splitlines():
                            if "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip() == "OPENAI_API_KEY" and self.provider in ("openai", "openai-local"):
                                    self.api_key = v.strip()
                                elif k.strip() == "ANTHROPIC_API_KEY" and self.provider == "anthropic":
                                    self.api_key = v.strip()
                                elif k.strip() == "GEMINI_API_KEY" and self.provider == "gemini":
                                    self.api_key = v.strip()
            except Exception:
                pass
                
        if not self.provider:
            self.provider = "ollama"

        if not self.api_key and self.provider in ("openai", "openai-local"):
            self.api_key = self._resolve_api_key()

        self._client = httpx.Client(timeout=timeout)

    def _resolve_api_key(self) -> str | None:
        """Resolve API keys for OpenAI-compatible endpoints without storing secrets in config."""
        key_names = ["OPENAI_API_KEY"]
        if self.provider == "openai-local":
            key_names.insert(0, "LOCAL_LLM_API_KEY")

        for key in key_names:
            value = os.getenv(key)
            if value:
                return value

        env_file = os.environ.get("ENV_FILE_PATH")
        env_paths = []
        if env_file:
            env_paths.append(Path(env_file))
        env_paths.append(Path.home() / ".hermes" / ".env")

        for env_path in env_paths:
            if not env_path.exists():
                continue
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.split("=", 1)
                if k.strip() in key_names and v.strip():
                    return v.strip()
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # -----------------------------------------------------------------
    # Health / liveness
    # -----------------------------------------------------------------

    def ping(self) -> bool:
        """True if server is reachable. Does not check model availability."""
        try:
            if self.provider == "ollama":
                r = self._client.get(f"{self.host}/api/tags", timeout=5.0)
            elif self.provider in ("openai", "openai-local"):
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                r = self._client.get(f"{self.host}/models", headers=headers, timeout=5.0)
            else:
                return True
            return r.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
            return False

    def list_models(self) -> list[str]:
        """List models available in this instance."""
        try:
            if self.provider == "ollama":
                r = self._client.get(f"{self.host}/api/tags", timeout=5.0)
                r.raise_for_status()
                data = r.json()
                return [m.get("name", "") for m in data.get("models", [])]
            elif self.provider in ("openai", "openai-local"):
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                r = self._client.get(f"{self.host}/models", headers=headers, timeout=5.0)
                r.raise_for_status()
                data = r.json()
                return [m.get("id", "") for m in data.get("data", [])]
            return []
        except httpx.ConnectError as e:
            raise OllamaNotRunning(
                f"Cannot connect to {self.provider} at {self.host}. "
                f"Is the server running?"
            ) from e
        except httpx.HTTPError as e:
            raise LLMError(f"{self.provider} error: {e}") from e

    def ensure_ready(self) -> None:
        """Verify server is running and the configured model is available."""
        if not self.ping():
            raise OllamaNotRunning(
                f"{self.provider} isn't reachable at {self.host}.\n"
                f"Please verify your LLM host settings."
            )
        # Skip model check for remote endpoints (like openai) since listing models is not always accurate or needed
        if self.provider in ("openai", "openai-local") and "api.openai.com" in self.host:
            return
            
        models = self.list_models()
        # Match by exact name or prefix
        if not any(m == self.model or m.startswith(self.model) for m in models):
            raise ModelNotFound(
                f"Model '{self.model}' not found in {self.provider}.\n"
                f"Available: {', '.join(models) if models else '(none)'}\n"
                f"Please pull or load this model."
            )

    # -----------------------------------------------------------------
    # Chat (non-streaming)
    # -----------------------------------------------------------------

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        thinking: bool = False,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> str:
        """Non-streaming chat. Returns the full assistant message content."""
        if self.provider == "ollama":
            payload_messages = self._prepare_messages(messages, thinking=thinking)
            payload = {
                "model": self.model,
                "messages": payload_messages,
                "stream": False,
                "options": {"temperature": temperature},
            }
            if json_mode:
                payload["format"] = "json"

            try:
                r = self._client.post(f"{self.host}/api/chat", json=payload)
                r.raise_for_status()
            except httpx.ConnectError as e:
                raise OllamaNotRunning(f"Cannot connect to Ollama at {self.host}.") from e
            except httpx.HTTPStatusError as e:
                body = e.response.text
                if "not found" in body.lower() or e.response.status_code == 404:
                    raise ModelNotFound(f"Model '{self.model}' not found.") from e
                raise LLMError(f"Ollama error {e.response.status_code}: {body}") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Ollama request failed: {e}") from e

            data = r.json()
            content = data.get("message", {}).get("content", "")
            return self._strip_thinking(content)
            
        elif self.provider in ("openai", "openai-local"):
            payload_messages = [{"role": m.role, "content": m.content} for m in messages]
            payload = {
                "model": self.model,
                "messages": payload_messages,
                "temperature": temperature,
            }
            if json_mode:
                if self.provider == "openai-local":
                    # Some local OpenAI-compatible servers (LM Studio-compatible)
                    # reject OpenAI's legacy json_object mode and accept only
                    # text/json_schema. Keep transport compatible and rely on
                    # the extraction prompt's strict JSON instructions.
                    payload["response_format"] = {"type": "text"}
                else:
                    payload["response_format"] = {"type": "json_object"}

            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            try:
                r = self._client.post(f"{self.host}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._strip_thinking(content)
            except Exception as e:
                raise LLMError(f"OpenAI-compatible host error: {e}")
                
        return ""

    # -----------------------------------------------------------------
    # Chat (streaming)
    # -----------------------------------------------------------------

    def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        thinking: bool = False,
        temperature: float = 0.3,
    ) -> Generator[str, None, str]:
        """Streaming chat. Yields content chunks as they arrive."""
        if self.provider == "ollama":
            payload_messages = self._prepare_messages(messages, thinking=thinking)
            payload = {
                "model": self.model,
                "messages": payload_messages,
                "stream": True,
                "options": {"temperature": temperature},
            }

            full_content: list[str] = []
            in_thinking_block = False

            try:
                with self._client.stream("POST", f"{self.host}/api/chat", json=payload) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        msg = data.get("message", {})
                        chunk = msg.get("content", "")
                        if not chunk:
                            if data.get("done"):
                                break
                            continue

                        # Strip thinking blocks on the fly
                        visible = ""
                        i = 0
                        while i < len(chunk):
                            if not in_thinking_block:
                                start = chunk.find("<think>", i)
                                if start == -1:
                                    visible += chunk[i:]
                                    break
                                visible += chunk[i:start]
                                in_thinking_block = True
                                i = start + len("<think>")
                            else:
                                end = chunk.find("</think>", i)
                                if end == -1:
                                    break
                                in_thinking_block = False
                                i = end + len("</think>")

                        if visible:
                            full_content.append(visible)
                            yield visible

                        if data.get("done"):
                            break
            except httpx.ConnectError as e:
                raise OllamaNotRunning(f"Cannot connect to Ollama at {self.host}.") from e
            except httpx.HTTPStatusError as e:
                body = e.response.read().decode(errors="replace") if e.response else ""
                raise LLMError(f"Ollama error {e.response.status_code}: {body}") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Ollama streaming failed: {e}") from e

            return "".join(full_content)
            
        elif self.provider in ("openai", "openai-local"):
            payload_messages = [{"role": m.role, "content": m.content} for m in messages]
            payload = {
                "model": self.model,
                "messages": payload_messages,
                "temperature": temperature,
                "stream": True,
            }
            
            full_content: list[str] = []
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            try:
                with self._client.stream("POST", f"{self.host}/chat/completions", json=payload, headers=headers) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(line)
                            chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if chunk:
                                full_content.append(chunk)
                                yield chunk
                        except Exception:
                            continue
            except Exception as e:
                raise LLMError(f"OpenAI-compatible streaming failed: {e}")
            return "".join(full_content)
            
        return ""

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _prepare_messages(
        self, messages: list[ChatMessage], *, thinking: bool
    ) -> list[dict]:
        """Convert to Ollama's wire format and append the Qwen3 thinking tag."""
        result = [{"role": m.role, "content": m.content} for m in messages]
        if result:
            tag = "\n\n/think" if thinking else "\n\n/no_think"
            # Only append to the last user message (Qwen3 convention)
            for i in range(len(result) - 1, -1, -1):
                if result[i]["role"] == "user":
                    result[i]["content"] += tag
                    break
        return result

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove <think>...</think> blocks from a completed response."""
        if "<think>" not in text:
            return text
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
