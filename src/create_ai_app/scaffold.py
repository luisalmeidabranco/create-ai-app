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
        monorepo, precommit, teams,
    )

    target = Path.cwd() / cfg.name
    if target.exists():
        console.print(f"[red]Error:[/red] Directory [bold]{cfg.name}[/bold] already exists.")
        return

    target.mkdir(parents=True)

    # ── build step list ───────────────────────────────────────────────────────
    steps: list[tuple[str, callable]] = []

    if cfg.is_monorepo:
        steps.append(("Monorepo workspace", lambda: monorepo.install(cfg, target)))
        for app_name in cfg.monorepo_apps:
            if app_name == "REST API":
                steps.append((f"apps/api  (REST API)", lambda: _scaffold_app(cfg, target, "REST API")))
            elif app_name == "Agent":
                steps.append((f"apps/agent  (Agent)", lambda: _scaffold_app(cfg, target, "Agent")))
            elif app_name == "Teams Bot":
                steps.append((f"apps/teams-frontdoor", lambda: teams.install_app(cfg, target / "apps" / "teams-frontdoor")))
            elif app_name == "Batch":
                steps.append((f"apps/pipeline  (Batch)", lambda: _scaffold_app(cfg, target, "Batch / CronJob")))
    else:
        steps.append(("Base files", lambda: base.install(cfg, target)))
        if cfg.is_rest_api:
            steps.append(("REST API (FastAPI)", lambda: api.install(cfg, target)))
        elif cfg.is_agent:
            steps.append(("Agent structure", lambda: agent.install(cfg, target)))
        elif cfg.is_teams:
            steps.append(("Teams Bot", lambda: teams.install(cfg, target)))
        elif cfg.is_batch:
            steps.append(("Batch processor", lambda: batch.install(cfg, target)))

        if cfg.has_api and cfg.auth != "None":
            steps.append(("Auth middleware", lambda: auth.install(cfg, target)))

        if cfg.database != "None — stateless":
            steps.append(("Database adapter", lambda: database.install(cfg, target)))

    steps.append(("Logging config", lambda: logging_installer.install(cfg, target)))

    if cfg.frontend != "None" and not cfg.is_monorepo:
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


def _scaffold_app(cfg: ProjectConfig, target: Path, app_type_override: str) -> None:
    """Install one app inside a monorepo's apps/ directory."""
    from create_ai_app.installers import agent, api, batch, base
    import copy

    app_dir_map = {
        "REST API": target / "apps" / "api",
        "Agent": target / "apps" / "agent",
        "Batch / CronJob": target / "apps" / "pipeline",
    }
    app_dir = app_dir_map.get(app_type_override, target / "apps" / "app")
    app_dir.mkdir(parents=True, exist_ok=True)

    sub_cfg = copy.copy(cfg)
    sub_cfg.app_type = app_type_override
    sub_cfg.name = app_dir.name
    sub_cfg.infra = "None"   # infra lives at monorepo root, not in each app
    sub_cfg.git = False
    sub_cfg.precommit = False

    base.install(sub_cfg, app_dir)
    if app_type_override == "REST API":
        api.install(sub_cfg, app_dir)
    elif app_type_override == "Agent":
        agent.install(sub_cfg, app_dir)
    elif app_type_override == "Batch / CronJob":
        batch.install(sub_cfg, app_dir)


def _git_init(target: Path) -> None:
    subprocess.run(["git", "init", str(target)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(target), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(target), "commit", "-m", "chore: initial scaffold via create-ai-app"],
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
    """Print a rich tree of the generated project (excluding .venv and .git)."""
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
    lines = [f"  cd {cfg.name}", "  cp .env.example .env   [dim]# fill in credentials[/dim]"]

    if cfg.is_rest_api:
        lines.append("  uv run uvicorn main:app --reload --port 3100")
    elif cfg.is_teams:
        lines.append("  uv run python -m aiohttp.web src.{cfg.pkg_name}.app:create_app")
    elif cfg.is_batch:
        lines.append(f"  uv run python -m {cfg.pkg_name}.cli --help")
    elif cfg.is_agent and cfg.api_framework == "Chainlit":
        lines.append("  uv run chainlit run main.py")
    elif cfg.is_monorepo:
        lines.append("  # start each app independently — see apps/*/README or run uv run in each")
    else:
        lines.append(f"  uv run python -m {cfg.pkg_name}")

    if cfg.docker and not cfg.is_monorepo:
        lines.append(f"  docker build -t {cfg.name} .")
        port = "3978" if cfg.is_teams else "3100"
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
