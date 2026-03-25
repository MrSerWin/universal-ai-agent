"""Configuration loader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    name: str
    ollama_tag: str
    context_length: int
    description: str
    roles: list[str] = field(default_factory=list)


@dataclass
class Config:
    models: dict[str, ModelConfig] = field(default_factory=dict)
    routing_strategy: str = "auto"
    complexity_map: dict[str, str] = field(default_factory=dict)
    server_host: str = "0.0.0.0"
    server_port: int = 8800
    ollama_host: str = "http://localhost:11434"
    project_dir: Path = field(default_factory=lambda: Path.cwd())

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        config_path = Path(config_path)

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        models: dict[str, ModelConfig] = {}
        for key, val in raw.get("models", {}).items():
            models[key] = ModelConfig(
                name=val["name"],
                ollama_tag=val["ollama_tag"],
                context_length=val["context_length"],
                description=val["description"],
                roles=val.get("roles", []),
            )

        routing = raw.get("routing", {})
        server = raw.get("server", {})

        return cls(
            models=models,
            routing_strategy=routing.get("strategy", "auto"),
            complexity_map=routing.get("complexity_threshold", {}),
            server_host=server.get("host", "0.0.0.0"),
            server_port=server.get("port", 8800),
            ollama_host=os.environ.get(
                "OLLAMA_HOST", server.get("ollama_host", "http://localhost:11434")
            ),
        )

    def get_model(self, role: str) -> ModelConfig:
        """Get model config for a given role based on routing strategy."""
        if self.routing_strategy == "primary_only":
            return self.models["primary"]
        if self.routing_strategy == "fast_only":
            return self.models["fast"]
        if self.routing_strategy == "alternative":
            return self.models.get("alternative", self.models["primary"])

        # Auto routing
        for complexity, model_key in self.complexity_map.items():
            if model_key in self.models:
                model = self.models[model_key]
                if role in model.roles:
                    return model

        # Fallback: find first model that has the role
        for model in self.models.values():
            if role in model.roles:
                return model

        return self.models.get("primary", list(self.models.values())[0])
