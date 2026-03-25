"""CLI entry point — `aide` command."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .agent import Agent
from .config import Config

console = Console()


def get_agent(project_dir: str | None = None) -> Agent:
    config = Config.load()
    p = Path(project_dir) if project_dir else Path.cwd()
    return Agent(config, project_dir=p)


@click.group()
@click.version_option(version="0.1.0", prog_name="aide")
def cli():
    """aide — Local AI Code Agent"""
    pass


@cli.command()
@click.argument("project_dir", default=".", type=click.Path(exists=True))
def init(project_dir: str):
    """Initialize AI agent for a project. Indexes the codebase for RAG."""
    agent = get_agent(project_dir)
    console.print(Panel(f"Initializing aide for: [bold]{agent.project_dir}[/bold]", style="blue"))

    async def _init():
        # Check Ollama health
        healthy = await agent.llm.check_health()
        if not healthy:
            console.print("[red]Ollama is not running![/red] Start it with: ollama serve")
            return

        models = await agent.llm.list_models()
        console.print(f"Available models: {', '.join(models)}")

        # TODO: Run RAG indexer
        console.print("[yellow]RAG indexing not yet implemented.[/yellow]")
        console.print("[green]Project initialized.[/green]")
        await agent.llm.close()

    asyncio.run(_init())


@cli.command()
@click.argument("file_path", required=False, type=click.Path())
@click.option("--all", "review_all", is_flag=True, help="Review all changed files (git diff)")
def review(file_path: str | None, review_all: bool):
    """Review code for bugs, quality, and best practices."""
    agent = get_agent()

    async def _review():
        healthy = await agent.llm.check_health()
        if not healthy:
            console.print("[red]Ollama is not running![/red]")
            return

        if review_all:
            diff_result = await agent.tools.execute("git", {"args": "diff"})
            if not diff_result.strip() or '"stdout": ""' in diff_result:
                diff_result = await agent.tools.execute("git", {"args": "diff --cached"})
            code = diff_result
            label = "git diff"
        elif file_path:
            code = await agent.tools.execute("read_file", {"path": file_path})
            label = file_path
        else:
            console.print("[red]Provide a file path or use --all[/red]")
            return

        # Load review prompt
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "review.md"
        review_prompt = prompt_path.read_text() if prompt_path.exists() else "Review this code:"

        full_prompt = f"{review_prompt}\n\n```\n{code}\n```"

        console.print(Panel(f"Reviewing: [bold]{label}[/bold]", style="blue"))
        response = ""
        async for token in agent.chat(full_prompt, command="review"):
            response += token
            print(token, end="", flush=True)
        print()
        await agent.llm.close()

    asyncio.run(_review())


@cli.command()
@click.argument("file_path", required=False, type=click.Path())
def security(file_path: str | None):
    """Run a security audit on code."""
    agent = get_agent()

    async def _security():
        healthy = await agent.llm.check_health()
        if not healthy:
            console.print("[red]Ollama is not running![/red]")
            return

        if file_path:
            code = await agent.tools.execute("read_file", {"path": file_path})
        else:
            # Security scan on all staged/changed files
            code = await agent.tools.execute("git", {"args": "diff"})

        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "security.md"
        sec_prompt = prompt_path.read_text() if prompt_path.exists() else "Security audit:"

        full_prompt = f"{sec_prompt}\n\n```\n{code}\n```"

        console.print(Panel("Security Audit", style="red"))
        async for token in agent.chat(full_prompt, command="security"):
            print(token, end="", flush=True)
        print()
        await agent.llm.close()

    asyncio.run(_security())


@cli.command()
@click.option("--project", "-p", type=click.Path(exists=True), default=".")
@click.option("--tools/--no-tools", "use_tools", default=True, help="Enable/disable tool use")
def chat(project: str, use_tools: bool):
    """Interactive chat with the AI agent."""
    agent = get_agent(project)

    console.print(Panel(
        "[bold]aide[/bold] — Local AI Code Agent\n"
        f"Project: {agent.project_dir}\n"
        f"Model routing: {agent.config.routing_strategy}\n"
        "Type 'exit' or 'quit' to leave. '/clear' to reset context.",
        style="blue",
    ))

    async def _chat():
        healthy = await agent.llm.check_health()
        if not healthy:
            console.print("[red]Ollama is not running![/red] Start it: ollama serve")
            return

        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]you[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                console.print("\nBye!")
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() in ("exit", "quit"):
                console.print("Bye!")
                break
            if user_input.strip() == "/clear":
                agent.reset_conversation()
                console.print("[dim]Context cleared.[/dim]")
                continue
            if user_input.strip() == "/model":
                models = await agent.llm.list_models()
                console.print(f"Available: {', '.join(models)}")
                continue

            console.print("[bold green]aide[/bold green]:", end=" ")

            if use_tools:
                response = await agent.chat_with_tools(user_input)
                console.print(Markdown(response))
            else:
                async for token in agent.chat(user_input):
                    print(token, end="", flush=True)
                print()

        await agent.llm.close()

    asyncio.run(_chat())


@cli.command()
@click.option("--message", "-m", default=None, help="Commit message (auto-generated if empty)")
def commit(message: str | None):
    """Generate a commit message and commit staged changes."""
    agent = get_agent()

    async def _commit():
        healthy = await agent.llm.check_health()
        if not healthy:
            console.print("[red]Ollama is not running![/red]")
            return

        diff = await agent.tools.execute("git", {"args": "diff --cached"})
        if '"stdout": ""' in diff or not diff.strip():
            console.print("[yellow]No staged changes. Stage files first: git add <files>[/yellow]")
            return

        if message is None:
            prompt = (
                "Generate a concise git commit message for these changes. "
                "Follow conventional commits format (feat/fix/refactor/docs/etc). "
                "Output ONLY the commit message, nothing else.\n\n"
                f"```diff\n{diff}\n```"
            )
            msg = await agent.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                role="commit_messages",
                max_tokens=200,
            )
            msg = msg.strip().strip('"').strip("'").strip("`")
        else:
            msg = message

        console.print(f"\nCommit message: [bold]{msg}[/bold]")
        confirm = Prompt.ask("Commit?", choices=["y", "n"], default="y")
        if confirm == "y":
            result = await agent.tools.execute("git", {"args": f'commit -m "{msg}"'})
            console.print(result)

        await agent.llm.close()

    asyncio.run(_commit())


@cli.command()
def status():
    """Show agent status — models, health, project info."""
    config = Config.load()

    async def _status():
        from .llm import LLMClient
        llm = LLMClient(config)

        healthy = await llm.check_health()
        status_icon = "[green]running[/green]" if healthy else "[red]stopped[/red]"

        info_lines = [
            f"Ollama: {status_icon} ({config.ollama_host})",
            f"Routing: {config.routing_strategy}",
            "",
            "[bold]Configured models:[/bold]",
        ]

        available = await llm.list_models() if healthy else []
        for key, model in config.models.items():
            installed = any(model.ollama_tag in m for m in available)
            icon = "[green]v[/green]" if installed else "[red]x[/red]"
            info_lines.append(f"  {icon} [{key}] {model.name} — {model.description}")

        console.print(Panel("\n".join(info_lines), title="aide status", style="blue"))
        await llm.close()

    asyncio.run(_status())


if __name__ == "__main__":
    cli()
