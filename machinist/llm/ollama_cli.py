from __future__ import annotations

import subprocess
from typing import Any, Iterable, List, Optional

from .base import LLMClient


class OllamaClient(LLMClient):
    """
    Minimal Ollama CLI client using `ollama run`. Requires the model to be pulled already.
    """

    def __init__(self, model: str) -> None:
        self._model = model
        if subprocess.run(["which", "ollama"], capture_output=True, text=True).returncode != 0:
            raise RuntimeError("ollama CLI not found on PATH. Install Ollama and ensure the CLI is available.")

    def _invoke(self, prompt: str, *, temperature: float = 0.0, max_tokens: Optional[int] = None, timeout: int = 600) -> str:
        # Minimal invocation for broad Ollama CLI compatibility; send prompt via stdin.
        cmd = ["ollama", "run", self._model]
        res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            raise RuntimeError(f"Ollama call failed: {res.stderr.strip()}")
        return res.stdout.strip()

    def stream_complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_token: Optional[callable] = None,
        timeout: float = 600,
    ) -> str:
        composed = f"System:\n{system}\n\nUser:\n{prompt}"
        cmd = ["ollama", "run", self._model]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert proc.stdin is not None
        proc.stdin.write(composed)
        proc.stdin.close()
        output_parts: List[str] = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if not line:
                    break
                output_parts.append(line)
                if on_token:
                    on_token(line)
        finally:
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError("Ollama call timed out")
        if proc.returncode != 0:
            stderr = (proc.stderr.read() if proc.stderr else "").strip()
            raise RuntimeError(f"Ollama call failed: {stderr}")
        return "".join(output_parts).strip()

    def complete(self, system: str, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        composed = f"System:\n{system}\n\nUser:\n{prompt}"
        return self._invoke(composed, temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages: List[dict[str, str]], *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        rendered = "\n".join(f"{m['role'].capitalize()}:\n{m['content']}" for m in messages)
        return self._invoke(rendered, temperature=temperature, max_tokens=max_tokens)

    def model_name(self) -> str:
        return self._model


class FallbackOllamaClient(LLMClient):
    """
    Tries a list of models in order until one succeeds. Useful for resilience when a model
    is unavailable or returns empty output.
    """

    def __init__(self, models: List[str]) -> None:
        if not models:
            raise ValueError("At least one model is required for fallback.")
        self._models = models
        if subprocess.run(["which", "ollama"], capture_output=True, text=True).returncode != 0:
            raise RuntimeError("ollama CLI not found on PATH. Install Ollama and ensure the CLI is available.")

    def _try_models(self, render: callable) -> str:
        errors: List[str] = []
        for model in self._models:
            cmd, prompt = render(model)
            res = subprocess.run(cmd, input=prompt, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                self._last_model = model
                return res.stdout.strip()
            errors.append(res.stderr.strip() or f"{model} returned empty output")
        raise RuntimeError(f"All models failed: {' | '.join(errors)}")

    def complete(self, system: str, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        composed = f"System:\n{system}\n\nUser:\n{prompt}"

        def render(model: str):
            cmd = ["ollama", "run", model]
            return cmd, composed

        return self._try_models(render)

    def chat(self, messages: List[dict[str, str]], *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        rendered = "\n".join(f"{m['role'].capitalize()}:\n{m['content']}" for m in messages)

        def render(model: str):
            cmd = ["ollama", "run", model]
            return cmd, rendered

        return self._try_models(render)

    def model_name(self) -> str:
        return getattr(self, "_last_model", self._models[0])

    def stream_complete(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_token: Optional[callable] = None,
        timeout: float | None = None,
    ) -> str:
        composed = f"System:\n{system}\n\nUser:\n{prompt}"
        errors: List[str] = []
        for model in self._models:
            cmd = ["ollama", "run", model]
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdin is not None
                proc.stdin.write(composed)
                proc.stdin.close()
                output_parts: List[str] = []
                assert proc.stdout is not None
                for line in proc.stdout:
                    if not line:
                        break
                    output_parts.append(line)
                    if on_token:
                        on_token(line)
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    errors.append(f"{model} timed out")
                    continue
                if proc.returncode == 0 and "".join(output_parts).strip():
                    self._last_model = model
                    return "".join(output_parts).strip()
                stderr = (proc.stderr.read() if proc.stderr else "").strip()
                errors.append(stderr or f"{model} returned empty output")
            except Exception as exc:
                errors.append(str(exc))
                continue
        raise RuntimeError(f"All models failed: {' | '.join(errors)}")
