"""Code indexer — parses and chunks source files for RAG."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# File extensions we care about
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs",
    ".json", ".yaml", ".yml", ".toml",
    ".html", ".css", ".scss",
    ".md", ".txt",
    ".sh", ".bash",
    ".sql",
    ".dockerfile", ".dockerignore",
}

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target",
    ".mypy_cache", ".pytest_cache", ".tox",
    "coverage", ".coverage", ".nyc_output",
    "vendor", ".cargo",
}

# Max file size to index (500KB)
MAX_FILE_SIZE = 500_000


@dataclass
class CodeChunk:
    """A chunk of code with metadata."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # "function", "class", "module", "block"
    name: str = ""  # function/class name if applicable
    language: str = ""
    file_hash: str = ""

    @property
    def id(self) -> str:
        raw = f"{self.file_path}:{self.start_line}-{self.end_line}"
        return hashlib.md5(raw.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name,
            "language": self.language,
        }


class CodeIndexer:
    """Indexes a codebase into chunks suitable for RAG."""

    def __init__(self, project_dir: Path, chunk_size: int = 100, chunk_overlap: int = 20):
        self.project_dir = project_dir
        self.chunk_size = chunk_size  # lines per chunk
        self.chunk_overlap = chunk_overlap

    def discover_files(self) -> list[Path]:
        """Find all indexable source files."""
        files: list[Path] = []
        for root, dirs, filenames in os.walk(self.project_dir):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

            for fname in filenames:
                fp = Path(root) / fname
                if fp.suffix.lower() in CODE_EXTENSIONS and fp.stat().st_size <= MAX_FILE_SIZE:
                    files.append(fp)

        return sorted(files)

    def _detect_language(self, path: Path) -> str:
        ext_map = {
            ".py": "python", ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript", ".rs": "rust",
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml", ".html": "html", ".css": "css",
            ".scss": "scss", ".md": "markdown", ".sh": "bash",
            ".sql": "sql",
        }
        return ext_map.get(path.suffix.lower(), "text")

    def _file_hash(self, path: Path) -> str:
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()

    def chunk_file(self, file_path: Path) -> list[CodeChunk]:
        """Split a file into chunks using simple line-based splitting with overlap."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        lines = content.splitlines()
        if not lines:
            return []

        language = self._detect_language(file_path)
        rel_path = str(file_path.relative_to(self.project_dir))
        fhash = self._file_hash(file_path)

        # For small files, return as single chunk
        if len(lines) <= self.chunk_size:
            return [CodeChunk(
                content=content,
                file_path=rel_path,
                start_line=1,
                end_line=len(lines),
                chunk_type="module",
                name=file_path.name,
                language=language,
                file_hash=fhash,
            )]

        # Split into overlapping chunks
        chunks: list[CodeChunk] = []
        start = 0
        while start < len(lines):
            end = min(start + self.chunk_size, len(lines))
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)

            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=rel_path,
                start_line=start + 1,
                end_line=end,
                chunk_type="block",
                name=f"{file_path.name}:{start + 1}-{end}",
                language=language,
                file_hash=fhash,
            ))

            start += self.chunk_size - self.chunk_overlap

        return chunks

    def index_project(self) -> list[CodeChunk]:
        """Index the entire project into chunks."""
        files = self.discover_files()
        all_chunks: list[CodeChunk] = []

        for fp in files:
            chunks = self.chunk_file(fp)
            all_chunks.extend(chunks)

        return all_chunks

    def get_project_summary(self) -> str:
        """Generate a brief summary of the project structure."""
        files = self.discover_files()
        lang_counts: dict[str, int] = {}
        total_lines = 0

        for fp in files:
            lang = self._detect_language(fp)
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
            try:
                total_lines += sum(1 for _ in open(fp, errors="replace"))
            except Exception:
                pass

        summary_parts = [
            f"Project: {self.project_dir.name}",
            f"Files: {len(files)}",
            f"Lines: {total_lines:,}",
            "Languages:",
        ]
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
            summary_parts.append(f"  - {lang}: {count} files")

        return "\n".join(summary_parts)
