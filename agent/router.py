"""Model router — picks the right model based on task type."""

from __future__ import annotations

import re

from .config import Config, ModelConfig

# Keywords that indicate complexity level
SIMPLE_KEYWORDS = [
    "autocomplete", "complete", "commit message", "rename", "format",
    "import", "typo", "comment", "docstring", "type hint",
]

COMPLEX_KEYWORDS = [
    "architect", "design", "refactor entire", "migrate", "rewrite",
    "security audit", "performance audit", "multi-file", "from scratch",
    "ci/cd", "pipeline", "deploy", "infrastructure",
]

HEAVY_KEYWORDS = [
    "system design", "full architecture", "design from scratch",
    "migrate entire", "rewrite entire project", "plan the migration",
]


class ModelRouter:
    """Decides which model to use for a given task."""

    def __init__(self, config: Config):
        self.config = config

    def classify_task(self, user_input: str) -> str:
        """Classify task complexity: simple, medium, complex, heavy."""
        lower = user_input.lower()

        # Check heavy first (subset of complex, needs 70B)
        if "heavy" in self.config.models:
            for kw in HEAVY_KEYWORDS:
                if kw in lower:
                    return "heavy"

        for kw in COMPLEX_KEYWORDS:
            if kw in lower:
                return "complex"

        for kw in SIMPLE_KEYWORDS:
            if kw in lower:
                return "simple"

        # Heuristic: longer prompts tend to be more complex
        word_count = len(user_input.split())
        if word_count > 200:
            return "complex"
        if word_count < 20:
            return "simple"

        return "medium"

    def route(self, user_input: str, explicit_role: str | None = None) -> ModelConfig:
        """Pick the best model for this task."""
        strategy = self.config.routing_strategy

        if strategy == "primary_only":
            return self.config.models["primary"]
        if strategy == "fast_only":
            return self.config.models["fast"]
        if strategy == "alternative":
            return self.config.models.get("alternative", self.config.models["primary"])

        # Auto routing
        if explicit_role:
            return self.config.get_model(explicit_role)

        complexity = self.classify_task(user_input)
        model_key = self.config.complexity_map.get(complexity, "primary")

        if model_key in self.config.models:
            return self.config.models[model_key]

        return self.config.models["primary"]

    def get_role_for_command(self, command: str) -> str:
        """Map a CLI command to a model role."""
        command_role_map = {
            "chat": "code_generation",
            "review": "code_review",
            "security": "security_review",
            "refactor": "refactoring",
            "explain": "code_generation",
            "test": "code_generation",
            "commit": "commit_messages",
            "complete": "autocomplete",
            "init": "architecture",
            "debug": "debugging",
        }
        return command_role_map.get(command, "code_generation")
