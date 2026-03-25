"""RAG retriever — vector search over indexed code chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import Config
from ..llm import LLMClient
from .indexer import CodeChunk, CodeIndexer


class CodeRetriever:
    """Vector-based code retrieval using ChromaDB + Ollama embeddings."""

    def __init__(self, config: Config, project_dir: Path):
        self.config = config
        self.project_dir = project_dir
        self.llm = LLMClient(config)

        # ChromaDB persistent storage in project .aide directory
        self.db_path = project_dir / ".aide" / "chroma_db"
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="code_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    async def index_project(self, force: bool = False) -> int:
        """Index the entire project. Returns number of chunks indexed."""
        indexer = CodeIndexer(self.project_dir)

        if not force and self.collection.count() > 0:
            # Check if we need to re-index (simple: check file count)
            existing_files = set()
            results = self.collection.get(include=["metadatas"])
            if results["metadatas"]:
                for meta in results["metadatas"]:
                    existing_files.add(meta.get("file_path", ""))

            current_files = {
                str(f.relative_to(self.project_dir))
                for f in indexer.discover_files()
            }

            if existing_files == current_files:
                return self.collection.count()

        # Full re-index
        chunks = indexer.index_project()
        if not chunks:
            return 0

        # Generate embeddings in batches
        batch_size = 50
        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.content[:2000] for c in batch]  # Cap text length for embeddings

            embeddings = await self.llm.embed(texts)

            self.collection.upsert(
                ids=[c.id for c in batch],
                embeddings=embeddings,
                documents=[c.content for c in batch],
                metadatas=[
                    {
                        "file_path": c.file_path,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "chunk_type": c.chunk_type,
                        "name": c.name,
                        "language": c.language,
                    }
                    for c in batch
                ],
            )
            total_indexed += len(batch)

        return total_indexed

    async def search(
        self,
        query: str,
        n_results: int = 10,
        language_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for code chunks relevant to a query."""
        # Get query embedding
        query_embedding = (await self.llm.embed([query]))[0]

        where_filter = None
        if language_filter:
            where_filter = {"language": language_filter}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                hits.append({
                    "content": doc,
                    "file_path": meta["file_path"],
                    "start_line": meta["start_line"],
                    "end_line": meta["end_line"],
                    "name": meta.get("name", ""),
                    "language": meta.get("language", ""),
                    "relevance": 1 - dist,  # cosine distance to similarity
                })

        return hits

    async def get_context_for_query(self, query: str, max_tokens: int = 8000) -> str:
        """Get relevant code context formatted for LLM consumption."""
        hits = await self.search(query, n_results=15)

        context_parts: list[str] = []
        total_chars = 0
        char_limit = max_tokens * 4  # rough token-to-char ratio

        for hit in hits:
            if hit["relevance"] < 0.3:
                continue

            chunk_text = (
                f"### {hit['file_path']} (lines {hit['start_line']}-{hit['end_line']})\n"
                f"```{hit['language']}\n{hit['content']}\n```\n"
            )

            if total_chars + len(chunk_text) > char_limit:
                break

            context_parts.append(chunk_text)
            total_chars += len(chunk_text)

        if not context_parts:
            return ""

        return "## Relevant code from the project:\n\n" + "\n".join(context_parts)

    async def close(self):
        await self.llm.close()
