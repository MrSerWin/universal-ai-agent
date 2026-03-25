"""Core agent loop — orchestrates LLM + tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from .config import Config
from .llm import LLMClient
from .router import ModelRouter
from .tools.base import ToolRegistry


class Agent:
    """Main agent that processes user requests using LLM + tools."""

    def __init__(self, config: Config, project_dir: Path | None = None):
        self.config = config
        self.project_dir = project_dir or Path.cwd()
        self.llm = LLMClient(config)
        self.router = ModelRouter(config)
        self.tools = ToolRegistry(self.project_dir)
        self.conversation: list[dict] = []
        self._system_prompt: str | None = None

    def _load_system_prompt(self) -> str:
        if self._system_prompt:
            return self._system_prompt

        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "system.md"
        if prompt_path.exists():
            self._system_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            self._system_prompt = "You are a helpful coding assistant."

        # Append project context if available
        project_info = self._gather_project_context()
        if project_info:
            self._system_prompt += f"\n\n## Current Project\n{project_info}"

        return self._system_prompt

    def _gather_project_context(self) -> str:
        """Gather basic project info."""
        parts: list[str] = []
        parts.append(f"Working directory: {self.project_dir}")

        # Check for common project files
        markers = {
            "package.json": "Node.js/TypeScript project",
            "pyproject.toml": "Python project",
            "Cargo.toml": "Rust project",
            "go.mod": "Go project",
            "requirements.txt": "Python project",
        }
        for file, desc in markers.items():
            if (self.project_dir / file).exists():
                parts.append(f"Type: {desc} ({file} found)")

        # Git info
        git_dir = self.project_dir / ".git"
        if git_dir.exists():
            parts.append("Git: initialized")

        return "\n".join(parts)

    async def chat(self, user_message: str, command: str = "chat") -> AsyncIterator[str]:
        """Process a user message and yield response tokens."""
        # Route to the right model
        role = self.router.get_role_for_command(command)
        model = self.router.route(user_message, explicit_role=role)

        # Build messages
        system_msg = {"role": "system", "content": self._load_system_prompt()}
        self.conversation.append({"role": "user", "content": user_message})

        messages = [system_msg] + self.conversation

        # For now: simple streaming response without tool use
        # TODO: implement tool-calling loop when Ollama supports it natively
        full_response = ""
        async for token in self.llm.stream(
            messages=messages,
            model=model,
            role=role,
        ):
            full_response += token
            yield token

        self.conversation.append({"role": "assistant", "content": full_response})

    async def chat_with_tools(self, user_message: str, command: str = "chat") -> str:
        """Process a user message with tool-calling loop (non-streaming)."""
        role = self.router.get_role_for_command(command)
        model = self.router.route(user_message, explicit_role=role)

        system_prompt = self._load_system_prompt()
        system_prompt += "\n\n## Available Tools\n"
        system_prompt += "You can call tools by responding with JSON in this format:\n"
        system_prompt += '```json\n{"tool": "tool_name", "arguments": {...}}\n```\n'
        system_prompt += "\nAvailable tools:\n"
        for schema in self.tools.get_tool_schemas():
            fn = schema["function"]
            system_prompt += f"- **{fn['name']}**: {fn['description']}\n"
            for param, info in fn["parameters"].get("properties", {}).items():
                required = param in fn["parameters"].get("required", [])
                req_str = " (required)" if required else ""
                system_prompt += f"  - `{param}`: {info.get('description', '')}{req_str}\n"

        system_prompt += "\nAfter using a tool, you'll receive the result. Use multiple tools as needed."
        system_prompt += "\nWhen done, respond normally without tool calls."

        self.conversation.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": system_prompt}] + self.conversation

        max_iterations = 15
        for _ in range(max_iterations):
            response = await self.llm.generate(
                messages=messages,
                model=model,
                role=role,
                max_tokens=4096,
            )

            # Try to extract tool call from response
            tool_call = self._extract_tool_call(response)
            if tool_call is None:
                # No tool call — this is the final response
                self.conversation.append({"role": "assistant", "content": response})
                return response

            # Execute the tool
            tool_name = tool_call["tool"]
            tool_args = tool_call.get("arguments", {})
            tool_result = await self.tools.execute(tool_name, tool_args)

            # Add to conversation for next iteration
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"Tool result for `{tool_name}`:\n```\n{tool_result}\n```",
            })

        return "Max tool iterations reached. Please try a more specific request."

    def _extract_tool_call(self, response: str) -> dict | None:
        """Try to extract a tool call JSON from the response."""
        # Look for JSON blocks
        import re

        # Match ```json ... ``` blocks
        json_blocks = re.findall(r"```json\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                if "tool" in data:
                    return data
            except json.JSONDecodeError:
                continue

        # Try direct JSON parsing of the entire response
        try:
            data = json.loads(response.strip())
            if "tool" in data:
                return data
        except json.JSONDecodeError:
            pass

        return None

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation.clear()
        self._system_prompt = None
