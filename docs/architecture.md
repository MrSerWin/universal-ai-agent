# Architecture

## Overview

```
┌──────────────────────────────────────────────────────────┐
│                         User                             │
│               CLI (aide) / VS Code / API                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   CLI       │  │  VS Code     │  │  HTTP API      │  │
│  │  (Click)    │  │ (Continue.dev│  │  (future)      │  │
│  │             │  │  + Tasks)    │  │                │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│         └────────────────┼───────────────────┘           │
│                          │                               │
│  ┌───────────────────────▼──────────────────────────┐    │
│  │                    Agent                          │    │
│  │  Orchestrates LLM calls + tool execution          │    │
│  │  Manages conversation history                     │    │
│  │  Injects RAG context into prompts                 │    │
│  └──┬──────────────┬──────────────┬─────────────┘    │
│     │              │              │                    │
│  ┌──▼──────┐  ┌────▼─────┐  ┌────▼──────┐            │
│  │ Router  │  │   RAG    │  │  Tools    │            │
│  │         │  │          │  │           │            │
│  │ Model   │  │ ChromaDB │  │ read_file │            │
│  │ select  │  │ Embeddings│  │ write_file│            │
│  │ by task │  │ Indexer  │  │ edit_file │            │
│  │         │  │ Retriever│  │ search    │            │
│  │         │  │          │  │ git       │            │
│  │         │  │          │  │ shell     │            │
│  └──┬──────┘  └──────────┘  └───────────┘            │
│     │                                                 │
│  ┌──▼──────────────────────────────────────────┐      │
│  │              LLM Client                      │      │
│  │  httpx → Ollama API (localhost:11434)         │      │
│  │  Streaming / Non-streaming / Embeddings       │      │
│  └──────────────────────────────────────────────┘      │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                     Ollama Server                         │
│  ┌──────────────┐ ┌──────────┐ ┌───────────────────┐    │
│  │ Qwen2.5-32B  │ │ Qwen-7B  │ │ nomic-embed-text  │    │
│  │ (primary)    │ │ (fast)   │ │ (embedding)        │    │
│  └──────────────┘ └──────────┘ └───────────────────┘    │
│                     CUDA / NVIDIA GPU                      │
└──────────────────────────────────────────────────────────┘
```

## Components

### 1. CLI (`agent/cli.py`)

User-facing entry point. Built on Click + Rich.

**Responsibilities:**
- Parse commands and arguments
- Terminal output (formatting, Markdown, panels)
- Launch the async agent loop

**Data flow:**
```
User → CLI → Agent → LLM/Tools → CLI → User
```

### 2. Agent (`agent/agent.py`)

Core of the system. Orchestrates LLM interactions with tools.

**Responsibilities:**
- Manage conversation history
- Inject system prompt and project context
- Tool-calling loop: LLM requests tool → execute → result → LLM
- Iteration limit (max 15) to prevent infinite loops

**Two operating modes:**
- `chat()` — streaming without tools (fast response)
- `chat_with_tools()` — full agentic loop with tool-calling

### 3. Router (`agent/router.py`)

Selects the model based on the task.

**Classification logic:**
```
"rename variable"              → simple  → 7B (fast)
"review this function"         → medium  → 32B (primary)
"architect new microservice"   → complex → 32B (primary, full context)
```

**Strategies:**
- `auto` — automatic selection by keywords and query length
- `primary_only` — always 32B
- `fast_only` — always 7B
- `alternative` — always 16B (DeepSeek)

### 4. LLM Client (`agent/llm.py`)

HTTP client for the Ollama API.

**Methods:**
- `generate()` — complete response in a single request
- `stream()` — token-by-token streaming
- `embed()` — get embeddings for RAG
- `check_health()` — check Ollama availability
- `list_models()` — list installed models

**Request parameters:**
- `temperature: 0.1` — low for stable code output
- `num_ctx` — context window size (from model config)
- `num_predict` — max tokens in response
- `timeout: 300s` — 5 minutes for long generations

### 5. Tools (`agent/tools/base.py`)

Set of tools the agent can invoke.

| Tool | Description |
|------|-------------|
| `read_file` | Read a file (with line numbers, optional range) |
| `write_file` | Write a file (create or overwrite) |
| `edit_file` | Replace a specific string in a file |
| `list_files` | List files (with glob support) |
| `search_code` | Search file contents (grep -rn) |
| `run_command` | Execute a shell command |
| `git` | Git operations |

**Security:**
- Paths are resolved relative to project_dir
- Dangerous commands are blocked (`rm -rf /`, `mkfs`, etc.)
- Output is capped (500 files, 100 grep lines, 10KB stdout)

### 6. RAG System (`agent/rag/`)

System for understanding the entire project.

#### Indexer (`indexer.py`)

**Indexing pipeline:**
```
Project files → Filter → Read → Chunk → CodeChunk[]
```

- Scans the project, skipping node_modules, .git, etc.
- Supports: .py, .ts, .tsx, .js, .jsx, .rs, .json, .yaml, .html, .css, .md, .sql, .sh
- Files ≤100 lines → single chunk (module)
- Larger files → overlapping chunks of 100 lines with 20-line overlap

#### Retriever (`retriever.py`)

**Search pipeline:**
```
User query → Embedding → ChromaDB cosine search → Top-N chunks → LLM context
```

- Storage: ChromaDB (persistent, in `.aide/chroma_db/`)
- Embeddings: nomic-embed-text via Ollama
- Metric: cosine similarity
- Filtering: discards results with relevance < 0.3
- Context limit: ~8000 tokens (configurable)

### 7. Config (`agent/config.py`)

Loads YAML configuration into typed dataclasses.

**Priority:**
1. Environment variables (`OLLAMA_HOST`)
2. `config/models.yaml`
3. Default values

## Data Flow: Chat with Tools

```
1. User: "Find all TODOs in the project and fix them"
      │
2. Router: classify("Find all TODOs...") → medium → 32B
      │
3. Agent: build messages = [system_prompt + tools_schema + user_message]
      │
4. LLM (32B): → {"tool": "search_code", "arguments": {"pattern": "TODO"}}
      │
5. Agent: execute search_code → grep result
      │
6. Agent: append result to messages
      │
7. LLM (32B): → {"tool": "read_file", "arguments": {"path": "src/app.py"}}
      │
8. Agent: execute read_file → file contents
      │
9. Agent: append result to messages
      │
10. LLM (32B): → {"tool": "edit_file", "arguments": {...}}
      │
11. Agent: execute edit_file → OK
      │
12. LLM (32B): "Fixed 3 TODOs in src/app.py: ..."  (final response)
      │
13. CLI: display response to user
```

## Security

- All models run **locally** — data never leaves the machine
- Shell commands are filtered for dangerous patterns
- File operations are scoped to the project directory
- Ollama listens on `0.0.0.0` by default — accessible on LAN but **not on the internet**
- No API authentication (single-user mode)
