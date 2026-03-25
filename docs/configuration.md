# Configuration

All configuration lives in `config/models.yaml`.

## Config Structure

```yaml
models:
  primary:       # Primary model
  fast:          # Fast model
  alternative:   # Alternative model
  embedding:     # Embedding model

routing:
  strategy:      # Model selection strategy
  complexity_threshold:  # Complexity → model mapping

server:
  host:          # API host
  port:          # API port
  ollama_host:   # Ollama URL
```

## Models

### Model Fields

```yaml
models:
  primary:
    name: qwen2.5-coder:32b-instruct-q4_K_M   # Human-readable name
    ollama_tag: qwen2.5-coder:32b-instruct-q4_K_M  # Tag for ollama pull/run
    context_length: 32768                        # Context window size
    description: "Main coding model"             # Description
    roles:                                       # Which tasks this model handles
      - code_generation
      - code_review
      - refactoring
      - architecture
      - debugging
      - security_review
```

### Available Roles

| Role | Description | Typical Model |
|------|-------------|---------------|
| `code_generation` | Generate new code | primary / alternative |
| `code_review` | Review existing code | primary / alternative |
| `refactoring` | Refactor code | primary / alternative |
| `architecture` | Design architecture | primary |
| `debugging` | Find and fix bugs | primary / alternative |
| `security_review` | Security audit | primary |
| `routing` | Task classification | fast |
| `autocomplete` | Code autocompletion | fast |
| `classification` | Classification | fast |
| `small_edits` | Minor edits | fast |
| `commit_messages` | Generate commit messages | fast |
| `embedding` | Vector embeddings | embedding |

## Routing

### Strategies

```yaml
routing:
  strategy: auto  # auto | primary_only | fast_only | alternative
```

| Strategy | Description |
|----------|-------------|
| `auto` | Automatic model selection by task complexity |
| `primary_only` | Always use 32B |
| `fast_only` | Always use 7B |
| `alternative` | Always use 16B (DeepSeek) |

### Complexity Mapping

```yaml
routing:
  complexity_threshold:
    simple: fast        # Simple tasks → 7B
    medium: primary     # Medium tasks → 32B
    complex: primary    # Complex tasks → 32B
```

### How Complexity Is Determined

The router analyzes the query text:

**Simple** (→ fast/7B):
- Keywords: autocomplete, complete, commit message, rename, format, import, typo, comment, docstring, type hint
- Short queries (< 20 words)

**Complex** (→ primary/32B):
- Keywords: architect, design, refactor entire, migrate, rewrite, security audit, multi-file, from scratch, ci/cd, pipeline, deploy
- Long queries (> 200 words)

**Medium** (→ primary/32B):
- Everything else

## Switching to the 16B Model

For permanent switch:

```yaml
routing:
  strategy: alternative
```

To use 16B only for specific tasks:

```yaml
routing:
  strategy: auto
  complexity_threshold:
    simple: fast
    medium: alternative    # 16B for medium tasks
    complex: primary       # 32B only for complex tasks
```

## Environment Variables

| Variable | Description | Priority |
|----------|-------------|----------|
| `OLLAMA_HOST` | Ollama server URL | Higher than config |

```bash
# Example: connect to Ollama on another machine
OLLAMA_HOST=http://192.168.1.100:11434 aide chat
```

## Prompts

System prompts are stored in `config/prompts/`:

| File | Used by |
|------|---------|
| `system.md` | All commands (base system prompt) |
| `review.md` | `aide review` |
| `security.md` | `aide security` |

### Customizing Prompts

Edit the files directly. Format is Markdown. The agent injects the prompt as the system message.

```bash
# Edit the review prompt
nano config/prompts/review.md
```

### Adding a New Prompt

1. Create `config/prompts/my-command.md`
2. Add a command in `agent/cli.py` using existing commands as a template

## LLM Parameters

Generation parameters are set in code (`agent/llm.py`):

| Parameter | Value | Description |
|-----------|-------|-------------|
| `temperature` | `0.1` | Low for stable code output |
| `max_tokens` | `4096` | Max tokens in response |
| `timeout` | `300s` | Request timeout |

To change — edit the defaults in `agent/llm.py` or pass them via agent calls.
