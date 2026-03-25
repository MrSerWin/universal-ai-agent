# RAG System

RAG (Retrieval-Augmented Generation) allows the agent to understand the entire project, not just what fits into the model's context window.

## The Problem

- Qwen2.5-Coder-32B: 128K token context (effectively ~20K quality)
- Average project: 500K — 5M tokens
- You can't feed the entire project to the model in a single request

## The Solution

```
Entire project → Indexing → Chunks + Embeddings → ChromaDB
                                                      │
User query → Query embedding → Cosine search → Top-N chunks
                                                      │
                    System prompt + Relevant context + Query → LLM
```

## Components

### Indexer (`agent/rag/indexer.py`)

Responsible for scanning and chunking the codebase.

#### Supported Files

| Extension | Language |
|-----------|----------|
| `.py` | Python |
| `.ts`, `.tsx` | TypeScript |
| `.js`, `.jsx` | JavaScript |
| `.rs` | Rust |
| `.json` | JSON |
| `.yaml`, `.yml` | YAML |
| `.toml` | TOML |
| `.html` | HTML |
| `.css`, `.scss` | CSS |
| `.md`, `.txt` | Text |
| `.sh`, `.bash` | Shell |
| `.sql` | SQL |

#### Ignored Directories

```
node_modules, .git, __pycache__, .venv, venv,
dist, build, .next, .nuxt, target,
.mypy_cache, .pytest_cache, .tox,
coverage, .nyc_output, vendor, .cargo
```

#### Limits

- Max file size: **500KB**
- Max files in `list_files`: 500

#### Chunking Strategy

**Small files (≤100 lines):**
→ Single chunk of type `module` (entire file)

**Large files (>100 lines):**
→ Overlapping chunks:
- Chunk size: 100 lines
- Overlap: 20 lines

```
File (250 lines):
  Chunk 1: lines 1-100
  Chunk 2: lines 81-180     ← 20-line overlap with chunk 1
  Chunk 3: lines 161-250    ← 20-line overlap with chunk 2
```

The overlap ensures that functions/classes at chunk boundaries aren't lost.

#### Chunk Metadata

Each `CodeChunk` contains:

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | Code text |
| `file_path` | str | Relative file path |
| `start_line` | int | Start line |
| `end_line` | int | End line |
| `chunk_type` | str | `module` or `block` |
| `name` | str | Filename or `file.py:1-100` |
| `language` | str | Language (`python`, `typescript`, etc.) |
| `file_hash` | str | MD5 hash of the file (for change detection) |
| `id` | str | MD5 of `file_path:start-end` (unique ID) |

### Retriever (`agent/rag/retriever.py`)

Responsible for finding relevant chunks.

#### Storage

- **ChromaDB** — lightweight vector database
- Stored in `<project>/.aide/chroma_db/`
- Persistent (data survives restarts)
- Metric: **cosine similarity**

#### Embeddings

- Model: **nomic-embed-text** (~0.3GB)
- Dimensions: 768
- Via Ollama API (`/api/embeddings`)
- Text is truncated to 2000 characters before embedding

#### Indexing Process

```python
retriever = CodeRetriever(config, project_dir)
count = await retriever.index_project()
# count = number of indexed chunks
```

1. Indexer scans files and creates chunks
2. Chunks are sent for embedding in batches of 50
3. Embeddings + metadata are saved to ChromaDB
4. Re-indexing uses upsert (updates existing entries)

#### Incremental Indexing

When calling `index_project(force=False)`:
- Compares file list in DB with current files
- If they match — skips (already indexed)
- If they differ — full re-index

> TODO: Future — per-file hash checking for targeted updates

#### Search

```python
hits = await retriever.search("authentication middleware", n_results=10)
```

1. User query → embedding via nomic-embed-text
2. Cosine search in ChromaDB → Top-N results
3. Filter by relevance ≥ 0.3 (discard noise)
4. Optional language filter

#### Building LLM Context

```python
context = await retriever.get_context_for_query("how does auth work?", max_tokens=8000)
```

Produces a Markdown block with relevant code:

```markdown
## Relevant code from the project:

### src/auth/middleware.py (lines 1-45)
\```python
def authenticate(request):
    ...
\```

### src/auth/jwt.py (lines 10-60)
\```python
def verify_token(token):
    ...
\```
```

Limit: ~8000 tokens (configurable) to leave room for the model's response.

## Performance

| Project Size | Files | Chunks | Indexing Time | DB Size |
|-------------|-------|--------|---------------|---------|
| Small (100 files) | ~100 | ~150 | ~30 sec | ~5 MB |
| Medium (500 files) | ~500 | ~1000 | ~3 min | ~30 MB |
| Large (2000 files) | ~2000 | ~5000 | ~15 min | ~150 MB |

Time depends on embedding model speed. nomic-embed-text on GPU is fast.

## Limitations

1. **Line-based chunking** — simple but doesn't account for code structure (functions, classes). Future: tree-sitter AST parsing
2. **No incremental updates** — file changes require full re-indexing
3. **Embedding quality** — nomic-embed-text is good for text but not specialized for code
4. **Context window** — RAG pulls ~8K tokens, which may not be enough for complex cross-file tasks

## Planned Improvements

- [ ] Tree-sitter AST parsing for smart chunking (by functions/classes)
- [ ] Incremental indexing by file hashes
- [ ] Watchdog for automatic re-indexing on file changes
- [ ] Code-specific embedding model
- [ ] Hybrid search (vector + keyword BM25)
