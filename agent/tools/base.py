"""Base tool definitions for the agent."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class ToolRegistry:
    """Registry of all available tools the agent can use."""

    def __init__(self, project_dir: Path | None = None):
        self.project_dir = project_dir or Path.cwd()
        self._tools: dict[str, dict] = {}
        self._register_builtins()

    def _register_builtins(self):
        self._tools = {
            "read_file": {
                "description": "Read the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"},
                        "start_line": {"type": "integer", "description": "Start line (optional)"},
                        "end_line": {"type": "integer", "description": "End line (optional)"},
                    },
                    "required": ["path"],
                },
            },
            "write_file": {
                "description": "Write content to a file (creates or overwrites)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
            "edit_file": {
                "description": "Replace a specific string in a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "old_string": {"type": "string", "description": "Text to find"},
                        "new_string": {"type": "string", "description": "Text to replace with"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
            "list_files": {
                "description": "List files in a directory, optionally with a glob pattern",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                        "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                    },
                    "required": ["path"],
                },
            },
            "search_code": {
                "description": "Search for a pattern in files (grep)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern to search"},
                        "path": {"type": "string", "description": "Directory to search in"},
                        "file_glob": {"type": "string", "description": "File glob filter (e.g. '*.py')"},
                    },
                    "required": ["pattern"],
                },
            },
            "run_command": {
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to run"},
                        "cwd": {"type": "string", "description": "Working directory"},
                    },
                    "required": ["command"],
                },
            },
            "git": {
                "description": "Run a git command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "args": {"type": "string", "description": "Git arguments (e.g. 'status', 'diff HEAD')"},
                    },
                    "required": ["args"],
                },
            },
        }

    def get_tool_schemas(self) -> list[dict]:
        """Return tool schemas in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for name, tool in self._tools.items()
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name."""
        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = await handler(**arguments)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.project_dir / p
        return p.resolve()

    # ---- Tool implementations ----

    async def _exec_read_file(
        self, path: str, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        fp = self._resolve_path(path)
        if not fp.exists():
            return json.dumps({"error": f"File not found: {fp}"})
        text = fp.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        if start_line is not None or end_line is not None:
            s = (start_line or 1) - 1
            e = end_line or len(lines)
            lines = lines[s:e]
        numbered = [f"{i + (start_line or 1):>5} | {line}" for i, line in enumerate(lines)]
        return "".join(numbered)

    async def _exec_write_file(self, path: str, content: str) -> str:
        fp = self._resolve_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return json.dumps({"ok": True, "path": str(fp), "bytes": len(content)})

    async def _exec_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        fp = self._resolve_path(path)
        if not fp.exists():
            return json.dumps({"error": f"File not found: {fp}"})
        text = fp.read_text(encoding="utf-8")
        if old_string not in text:
            return json.dumps({"error": "old_string not found in file"})
        count = text.count(old_string)
        if count > 1:
            return json.dumps({"error": f"old_string found {count} times — must be unique"})
        new_text = text.replace(old_string, new_string, 1)
        fp.write_text(new_text, encoding="utf-8")
        return json.dumps({"ok": True, "replacements": 1})

    async def _exec_list_files(self, path: str, pattern: str | None = None) -> str:
        fp = self._resolve_path(path)
        if not fp.is_dir():
            return json.dumps({"error": f"Not a directory: {fp}"})
        if pattern:
            files = sorted(fp.glob(pattern))
        else:
            files = sorted(fp.iterdir())
        entries = []
        for f in files[:500]:  # cap at 500 entries
            entries.append({
                "name": f.name,
                "path": str(f.relative_to(self.project_dir)) if f.is_relative_to(self.project_dir) else str(f),
                "type": "dir" if f.is_dir() else "file",
                "size": f.stat().st_size if f.is_file() else None,
            })
        return json.dumps(entries, indent=2)

    async def _exec_search_code(
        self, pattern: str, path: str | None = None, file_glob: str | None = None
    ) -> str:
        search_dir = self._resolve_path(path) if path else self.project_dir
        cmd = ["grep", "-rn", "--color=never", "-E", pattern]
        if file_glob:
            cmd.extend(["--include", file_glob])
        cmd.append(str(search_dir))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace")
        # Limit output
        lines = output.splitlines()
        if len(lines) > 100:
            output = "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more matches)"
        return output or "(no matches)"

    async def _exec_run_command(self, command: str, cwd: str | None = None) -> str:
        work_dir = self._resolve_path(cwd) if cwd else self.project_dir
        # Security: block dangerous commands
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd"]
        for d in dangerous:
            if d in command:
                return json.dumps({"error": f"Blocked dangerous command: {command}"})

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
        )
        stdout, stderr = await proc.communicate()
        result = {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="replace")[:10000],
            "stderr": stderr.decode(errors="replace")[:5000],
        }
        return json.dumps(result)

    async def _exec_git(self, args: str) -> str:
        cmd = f"git {args}"
        return await self._exec_run_command(cmd)
