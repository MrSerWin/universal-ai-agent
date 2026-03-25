# VS Code Integration

Two options: **Continue.dev** (recommended) or **VS Code Tasks**.

## Option 1: Continue.dev (Recommended)

[Continue.dev](https://continue.dev) is an open-source VS Code extension that works with local models via Ollama.

### Installation

```bash
# In VS Code
ext install Continue.continue
```

Or via UI: Extensions → search "Continue" → Install.

### Configuration

Continue stores its config in `~/.continue/config.json`. Replace the contents with:

```json
{
  "models": [
    {
      "title": "aide-32B",
      "provider": "ollama",
      "model": "qwen2.5-coder:32b-instruct-q4_K_M",
      "apiBase": "http://localhost:11434",
      "contextLength": 32768
    },
    {
      "title": "aide-7B-fast",
      "provider": "ollama",
      "model": "qwen2.5-coder:7b-instruct-q8_0",
      "apiBase": "http://localhost:11434",
      "contextLength": 32768
    }
  ],
  "tabAutocompleteModel": {
    "title": "aide-autocomplete",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b-instruct-q8_0",
    "apiBase": "http://localhost:11434"
  },
  "embeddingsProvider": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "apiBase": "http://localhost:11434"
  },
  "allowAnonymousTelemetry": false
}
```

### Usage

| Shortcut | Action |
|----------|--------|
| `Ctrl+L` | Open chat with the model |
| `Ctrl+I` | Inline edit selected code |
| `Tab` | Accept autocomplete suggestion |
| `Ctrl+Shift+L` | Add a file to chat context |

### Continue.dev Features

- **Chat** — ask questions about code, request generation
- **Inline Edit** — select code, press Ctrl+I, describe the change
- **Autocomplete** — Tab completion from the 7B model (fast)
- **@-mentions** — `@file`, `@folder`, `@codebase` for context
- **RAG over codebase** — via built-in embeddings provider

### WSL: Connecting from Windows VS Code

If VS Code is on Windows and Ollama is in WSL:

1. Find the WSL IP:
```bash
# Inside WSL
hostname -I
```

2. In Continue settings, replace `localhost` with the WSL IP:
```json
"apiBase": "http://172.x.x.x:11434"
```

Or use the **Remote - WSL** extension:
- Install `ms-vscode-remote.remote-wsl`
- Open project via WSL: run `code .` in the WSL terminal
- Continue will automatically connect to `localhost:11434`

## Option 2: VS Code Tasks

Use the aide CLI directly from VS Code.

### Setup

Copy `vscode-extension/tasks.json` into your project:

```bash
mkdir -p /path/to/your/project/.vscode
cp ~/aide/vscode-extension/tasks.json /path/to/your/project/.vscode/tasks.json
```

### Available Tasks

| Task | Description |
|------|-------------|
| aide: Review Current File | Review the open file |
| aide: Security Audit Current File | Security audit the open file |
| aide: Review All Changes | Review git diff |
| aide: Smart Commit | Auto-generate commit |
| aide: Chat (Interactive) | Interactive chat in terminal |
| aide: Index Project | Index the project for RAG |

### Running Tasks

- `Ctrl+Shift+P` → "Tasks: Run Task" → select a task
- Or set up keyboard shortcuts in `keybindings.json`:

```json
[
  {
    "key": "ctrl+shift+r",
    "command": "workbench.action.tasks.runTask",
    "args": "aide: Review Current File"
  },
  {
    "key": "ctrl+shift+s",
    "command": "workbench.action.tasks.runTask",
    "args": "aide: Security Audit Current File"
  }
]
```

## Recommended Combo

Both options can be used **simultaneously**:

| Task | Tool |
|------|------|
| Autocomplete (Tab) | Continue.dev (7B) |
| Inline editing | Continue.dev (32B) |
| Code chat | Continue.dev (32B) |
| Code review | aide CLI (via Tasks) |
| Security audit | aide CLI (via Tasks) |
| Smart commit | aide CLI (via Tasks) |
| Project indexing | aide CLI (via Tasks) |
