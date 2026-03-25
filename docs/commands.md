# Commands Reference

## aide chat

Interactive chat with the AI agent.

```bash
aide chat [OPTIONS]
```

**Options:**
| Flag | Description | Default |
|------|-------------|---------|
| `--project`, `-p` | Path to project | `.` (current directory) |
| `--tools / --no-tools` | Enable/disable tool use | `--tools` |

**In-chat commands:**
| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation context |
| `/model` | Show available models |
| `exit`, `quit` | Exit chat |

**Examples:**

```bash
# Chat in current project
aide chat

# Chat for a specific project
aide chat -p /home/user/my-app

# Chat without tools (text only, faster)
aide chat --no-tools
```

**With tools (`--tools`, default):**
The agent can read/write files, search code, and execute commands. The response arrives after all actions are completed.

**Without tools (`--no-tools`):**
Pure streaming — response appears token by token. Faster, but the agent cannot interact with the file system.

---

## aide review

Code review a file or set of changes.

```bash
aide review [FILE_PATH] [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `FILE_PATH` | Path to file to review (optional) |

**Options:**
| Flag | Description |
|------|-------------|
| `--all` | Review all changes from `git diff` |

**What it checks:**
- Code quality (readability, DRY, complexity, dead code)
- Bugs and logic errors (off-by-one, null handling, race conditions)
- Security (injections, XSS, secrets in code)
- Performance (N+1 queries, memory leaks, unnecessary re-renders)

**Examples:**

```bash
# Review a specific file
aide review src/api/auth.py

# Review all uncommitted changes
aide review --all
```

**Output format:**

For each issue found:
```
File:Line — description
Severity: critical / warning / info
Fix: suggested fix
```

---

## aide security

Security audit of code.

```bash
aide security [FILE_PATH]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `FILE_PATH` | File to audit. Without argument — uses `git diff` |

**What it checks (OWASP Top 10):**
1. Injection (SQL, NoSQL, command, LDAP)
2. Authentication (weak auth, hardcoded credentials)
3. Authorization (IDOR, privilege escalation)
4. Data exposure (PII in logs, unencrypted storage)
5. Configuration (debug mode in prod, default creds, CORS)
6. Dependencies (known CVEs, outdated packages)
7. Cryptography (weak algorithms, hardcoded keys)
8. Input validation (missing sanitization)
9. Error handling (stack traces exposed in prod)
10. Secrets (API keys, tokens, passwords in code)

**Examples:**

```bash
# Audit a file
aide security src/api/auth.py

# Audit all changes
aide security
```

**Output format:**

```
[CRITICAL] SQL Injection in user query
Location: src/db/users.py:45
Description: User input directly interpolated into SQL query
Impact: Attacker can read/modify/delete any data in database
Fix: Use parameterized queries instead of string formatting
```

---

## aide commit

Auto-generate a commit message and commit staged changes.

```bash
aide commit [OPTIONS]
```

**Options:**
| Flag | Description |
|------|-------------|
| `-m`, `--message` | Specify message manually (skips generation) |

**Process:**
1. Reads `git diff --cached` (staged changes)
2. If nothing staged — warns the user
3. Generates a commit message via LLM (7B model, fast)
4. Displays the message and asks for confirmation
5. Commits

**Message format:**
Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`

**Examples:**

```bash
# Auto-generate
git add src/auth.py
aide commit

# Manual message
aide commit -m "fix: resolve race condition in session handler"
```

---

## aide init

Initialize the agent for a project. Indexes the codebase for RAG.

```bash
aide init [PROJECT_DIR]
```

**Arguments:**
| Argument | Description | Default |
|----------|-------------|---------|
| `PROJECT_DIR` | Path to project | `.` |

**What it does:**
1. Checks Ollama availability
2. Shows installed models
3. Runs RAG indexing of the project
4. Creates `.aide/` directory in the project

**Examples:**

```bash
# Initialize current project
aide init

# Initialize another project
aide init /home/user/my-react-app
```

---

## aide status

System diagnostics.

```bash
aide status
```

**Shows:**
- Ollama status (running/stopped)
- Configured models and their availability
- Current routing strategy

**Example output:**

```
╭──────── aide status ────────╮
│ Ollama: running (http://localhost:11434)
│ Routing: auto
│
│ Configured models:
│   ✓ [primary] qwen2.5-coder:32b — Main coding model
│   ✓ [fast] qwen2.5-coder:7b — Fast model
│   ✗ [alternative] deepseek-coder-v2:16b — Not installed
│   ✓ [embedding] nomic-embed-text — Embedding model
╰─────────────────────────────╯
```
