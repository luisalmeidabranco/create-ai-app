from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.tree import Tree

from create_ai_app.models import ProjectConfig

console = Console()


def scaffold_project(cfg: ProjectConfig) -> None:
    from create_ai_app.installers import (
        agent, api, auth, base, batch, database,
        docker, frontend, logging as logging_installer,
        precommit, teams,
    )

    target = Path.cwd() / cfg.name
    if target.exists():
        console.print(f"[red]Error:[/red] Directory [bold]{cfg.name}[/bold] already exists.")
        return

    target.mkdir(parents=True)

    # ── build step list ───────────────────────────────────────────────────────
    steps: list[tuple[str, callable]] = [
        ("Base files", lambda: base.install(cfg, target)),
    ]

    if cfg.is_rest_api:
        steps.append(("REST API (FastAPI)", lambda: api.install(cfg, target)))
    if cfg.is_agent:
        steps.append(("Agent structure", lambda: agent.install(cfg, target)))
    if cfg.is_teams:
        steps.append(("Teams Bot", lambda: teams.install(cfg, target)))
    if cfg.is_batch:
        steps.append(("Batch processor", lambda: batch.install(cfg, target)))

    if cfg.has_api and cfg.auth != "None":
        steps.append(("Auth middleware", lambda: auth.install(cfg, target)))

    if cfg.database != "None — stateless":
        steps.append(("Database adapter", lambda: database.install(cfg, target)))

    steps.append(("Logging config", lambda: logging_installer.install(cfg, target)))

    if cfg.frontend != "None":
        steps.append(("Frontend", lambda: frontend.install(cfg, target)))

    if cfg.docker:
        steps.append(("Docker", lambda: docker.install(cfg, target)))

    if cfg.precommit:
        steps.append(("Pre-commit hooks", lambda: precommit.install(cfg, target)))

    # ── execute with progress bar ─────────────────────────────────────────────
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scaffolding...", total=len(steps))
        for label, fn in steps:
            progress.update(task, description=f"[cyan]{label}[/cyan]")
            fn()
            progress.advance(task)

    console.print("[green]✓[/green] Scaffold complete")

    if cfg.git:
        _git_init(target)
        console.print("[green]✓[/green] Git repository initialised")

    _run_uv_sync(cfg, target)

    # ── file tree ─────────────────────────────────────────────────────────────
    _print_tree(cfg, target)
    _print_next_steps(cfg, target)


def _git_init(target: Path) -> None:
    subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(target), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(target), "commit", "-m", "chore: initial scaffold via new-ai-app"],
        check=True, capture_output=True,
    )


def _run_uv_sync(cfg: ProjectConfig, target: Path) -> None:
    if shutil.which("uv") is None:
        console.print("[yellow]⚠[/yellow]  uv not found — skipping sync. Install uv first.")
        return
    result = subprocess.run(["uv", "sync"], cwd=str(target), capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[yellow]⚠[/yellow]  uv sync warning:\n[dim]{result.stderr.strip()}[/dim]")
    else:
        console.print("[green]✓[/green] uv sync")


def _print_tree(cfg: ProjectConfig, target: Path) -> None:
    tree = Tree(f"[bold blue]{cfg.name}/[/bold blue]")
    _add_tree_nodes(tree, target, target)
    console.print()
    console.print(tree)
    console.print()


def _add_tree_nodes(node, base: Path, current: Path, depth: int = 0) -> None:
    if depth > 4:
        return
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return
    for entry in entries:
        if entry.name in (".git", ".venv", "__pycache__", "uv.lock", "node_modules"):
            continue
        if entry.is_dir():
            branch = node.add(f"[bold]{entry.name}/[/bold]")
            _add_tree_nodes(branch, base, entry, depth + 1)
        else:
            node.add(f"[dim]{entry.name}[/dim]")


def _print_next_steps(cfg: ProjectConfig, target: Path) -> None:
    lines = [
        f"  cd {cfg.name}",
        "  cp .env.example .env   [dim]# fill in credentials[/dim]",
        "  uv run pytest",
    ]

    if cfg.is_rest_api:
        lines.append("  uv run uvicorn main:app --reload --port 3100")
    elif cfg.is_teams:
        lines.append(f"  uv run python -m src.{cfg.pkg_name}.app")
    elif cfg.is_batch:
        lines.append(f"  uv run python -m {cfg.pkg_name}.cli --help")
    elif cfg.is_agent and cfg.api_framework == "Chainlit":
        lines.append("  uv run chainlit run main.py")
    else:
        lines.append(f"  uv run python -m {cfg.pkg_name}")

    if cfg.docker:
        lines.append(f"  docker build -t {cfg.name} .")
        port = "3978" if cfg.is_teams and not cfg.is_rest_api else "3100"
        lines.append(f"  docker run -p {port}:{port} --env-file .env {cfg.name}")

    if cfg.infra != "None":
        lines.append("  [dim]# run /az-setup to configure Azure deployment[/dim]")

    console.print(
        Panel("\n".join(lines), title="[bold green]Next steps[/bold green]", border_style="green")
    )
    console.print(
        f"[bold green]✓ Created[/bold green] [bold]{cfg.name}[/bold]  "
        f"[dim]{target}[/dim]\n"
    )
