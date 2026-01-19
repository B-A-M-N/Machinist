from __future__ import annotations

import json
import urllib.request
from typing import Any, List, Optional

from .base import LLMClient


class OllamaAPIClient(LLMClient):
    """
    Ollama client using the HTTP API for structured tool calling.
    """
    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self._model = model
        self._host = host.rstrip("/")

    def model_name(self) -> str:
        return self._model

    def complete(self, system: str, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages: List[dict[str, str]], *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            out = json.loads(resp.read().decode("utf-8"))

        return (out.get("message", {}) or {}).get("content", "") or ""

    def chat_with_tools(
        self,
        messages: List[dict[str, Any]], # messages can have tool_calls in them now
        *,
        tools: List[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def embeddings(self, prompt: str) -> List[float]:
        payload = {
            "model": self._model,
            "prompt": prompt
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._host}/api/embeddings",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return out.get("embedding", [])