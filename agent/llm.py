"""LLM client — talks to Ollama via OpenAI-compatible API."""

from __future__ import annotations

from typing import AsyncIterator

import httpx

from .config import Config, ModelConfig


class LLMClient:
    """Async client for Ollama's API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.ollama_host
        self._client = httpx.AsyncClient(timeout=300.0)

    async def close(self):
        await self._client.aclose()

    async def generate(
        self,
        messages: list[dict],
        model: ModelConfig | None = None,
        role: str = "code_generation",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a completion (non-streaming)."""
        if model is None:
            model = self.config.get_model(role)

        payload = {
            "model": model.ollama_tag,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": model.context_length,
            },
        }

        resp = await self._client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    async def stream(
        self,
        messages: list[dict],
        model: ModelConfig | None = None,
        role: str = "code_generation",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a completion token by token."""
        if model is None:
            model = self.config.get_model(role)

        payload = {
            "model": model.ollama_tag,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": model.context_length,
            },
        }

        async with self._client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                import json
                chunk = json.loads(line)
                if chunk.get("done"):
                    break
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings using the embedding model."""
        model = self.config.models.get("embedding")
        if model is None:
            raise ValueError("No embedding model configured")

        results = []
        for text in texts:
            resp = await self._client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model.ollama_tag, "prompt": text},
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

    async def check_health(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    async def list_models(self) -> list[str]:
        """List available models in Ollama."""
        resp = await self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
