from __future__ import annotations

from typing import Optional

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from create_ai_app.models import ProjectConfig
from create_ai_app.scaffold import scaffold_project

app = typer.Typer(
    name="create-ai-app",
    help="Interactive Python AI/GenAI project scaffolding CLI",
    add_completion=False,
)

console = Console()

# ── option lists ──────────────────────────────────────────────────────────────

_PYTHON_VERSIONS = [
    questionary.Choice("3.12  (recommended)", value="3.12"),
    questionary.Choice("3.13", value="3.13"),
    questionary.Choice("3.11", value="3.11"),
]

_STRUCTURE_TYPES = [
    questionary.Choice(
        "Single app",
        value="Single app",
        description="One service, one pyproject.toml — the standard starting point",
    ),
    questionary.Choice(
        "Monorepo",
        value="Monorepo",
        description="Multiple apps under apps/, one uv workspace — matches the elephant-path pattern",
    ),
]

_SINGLE_APP_TYPES = [
    questionary.Choice("REST API", value="REST API",
                       description="FastAPI backend with health endpoint, auth, and LLM service"),
    questionary.Choice("Agent", value="Agent",
                       description="Conversational agent with tool-calling, memory, and context providers"),
    questionary.Choice("Teams Bot", value="Teams Bot",
                       description="Microsoft Teams bot frontdoor — aiohttp adapter, port 3978"),
    questionary.Choice("Batch / CronJob", value="Batch / CronJob",
                       description="Script or scheduled job that processes data without a web server"),
]

_MONOREPO_APPS = [
    questionary.Choice("REST API (FastAPI)", value="REST API", checked=True),
    questionary.Choice("Agent", value="Agent", checked=False),
    questionary.Choice("Teams Bot frontdoor", value="Teams Bot", checked=False),
    questionary.Choice("Batch / CronJob", value="Batch", checked=False),
    questionary.Choice("Shared library", value="Shared", checked=False),
]

_LLM_BACKENDS = [
    questionary.Choice("Azure OpenAI  (recommended)", value="Azure OpenAI",
                       description="Direct SDK — no LangChain wrapper. Used in every production repo."),
    questionary.Choice("OpenAI.com", value="OpenAI.com",
                       description="OpenAI SDK pointed at api.openai.com"),
    questionary.Choice("Anthropic", value="Anthropic",
                       description="Anthropic SDK (Claude models)"),
    questionary.Choice("Multiple", value="Multiple",
                       description="Azure OpenAI primary + OpenAI/Anthropic fallback stubs"),
]

_AGENT_FRAMEWORKS = [
    questionary.Choice("None — raw SDK  (recommended)", value="None — raw SDK",
                       description="Direct openai.chat.completions — transparent, no magic"),
    questionary.Choice("Microsoft Agent Framework (MAF)", value="Microsoft AF",
                       description="agent_framework.azure — ContextProviders, HandoffBuilder, multi-agent"),
    questionary.Choice("LangGraph", value="LangGraph",
                       description="Graph-based agent orchestration from LangChain"),
    questionary.Choice("AutoGen", value="AutoGen",
                       description="Microsoft AutoGen multi-agent conversations"),
    questionary.Choice("LangChain", value="LangChain",
                       description="LangChain AgentExecutor + OpenAI Tools"),
]

_API_FRAMEWORKS = {
    "REST API": [
        questionary.Choice("FastAPI  (recommended)", value="FastAPI",
                           description="Async, Pydantic v2, automatic OpenAPI docs"),
        questionary.Choice("Flask", value="Flask",
                           description="Sync WSGI — simpler but no async"),
        questionary.Choice("None", value="None",
                           description="No web layer — library or background service"),
    ],
    "Agent": [
        questionary.Choice("Chainlit  (recommended)", value="Chainlit",
                           description="Chat UI framework built for LLM agents"),
        questionary.Choice("FastAPI + SSE", value="FastAPI",
                           description="Streaming API for custom frontends"),
        questionary.Choice("Streamlit", value="Streamlit",
                           description="Quick internal UI — no separate frontend project"),
        questionary.Choice("None", value="None",
                           description="Agent library only — integrate into your own entry point"),
    ],
}

_FRONTENDS = [
    questionary.Choice("None  (recommended for API-only)", value="None",
                       description="No separate frontend — API only or Teams Adaptive Cards"),
    questionary.Choice("Next.js 15 + TypeScript", value="Next.js 15",
                       description="React framework with App Router — asks about Tailwind + shadcn next"),
    questionary.Choice("Streamlit", value="Streamlit",
                       description="Python-native UI — no JS, great for internal dashboards"),
    questionary.Choice("Chainlit", value="Chainlit",
                       description="Chat UI for agent projects — markdown, code blocks, file uploads"),
]

_DATABASES = [
    questionary.Choice("None — stateless  (recommended)", value="None — stateless",
                       description="No persistence — scale horizontally without coordination"),
    questionary.Choice("Azure Cosmos DB", value="CosmosDB",
                       description="Serverless NoSQL — used for agent session state in all MAF repos"),
    questionary.Choice("PostgreSQL", value="PostgreSQL",
                       description="Relational — asyncpg + SQLAlchemy async ORM"),
    questionary.Choice("SQLite", value="SQLite",
                       description="File-based — good for local dev or single-instance batch"),
    questionary.Choice("Redis", value="Redis",
                       description="In-memory cache / pub-sub — fast ephemeral state"),
]

_AUTH_OPTIONS = [
    questionary.Choice("API key header  (recommended)", value="API key header",
                       description="X-API-Key header — simple, sufficient for service-to-service"),
    questionary.Choice("Azure Entra ID (JWT)", value="Azure Entra ID",
                       description="OAuth2 bearer token — for user-facing APIs"),
    questionary.Choice("None", value="None",
                       description="No auth — only for internal services behind a VPN/Teams"),
]

_LOGGING_STYLES = [
    questionary.Choice(
        "Console + rotating file  (recommended)", value="rotating",
        description="Logs to stdout and writes rotating app.log. Good for containers and VMs.",
    ),
    questionary.Choice(
        "Console only (simple)", value="basic",
        description="Single-line basicConfig. Good for scripts and local dev.",
    ),
    questionary.Choice(
        "Structured JSON", value="json",
        description="Machine-readable JSON lines. Best for Application Insights / log aggregation.",
    ),
]

_INFRA_OPTIONS = [
    questionary.Choice("Azure Container Apps — Bicep  (recommended)", value="Azure Container Apps — Bicep",
                       description="Serverless containers on ACA — matches bpo_email_int, alex-hr pattern"),
    questionary.Choice("AKS — Helm chart", value="AKS",
                       description="Kubernetes on AKS — matches the monorepo elephant-path pattern"),
    questionary.Choice("Azure Web App", value="Azure Web App",
                       description="PaaS App Service — simpler ops, less control"),
    questionary.Choice("None", value="None",
                       description="No infra scaffolding — deploy manually or via CI"),
]

_ENV_OPTIONS = [
    questionary.Choice("dev only", value="dev",
                       description="Prototype or single-person project"),
    questionary.Choice("dev + prd", value="dev,prd",
                       description="Small team, minimal pipeline"),
    questionary.Choice("dev + qa + prd  (recommended)", value="dev,qa,prd",
                       description="Standard enterprise: quality gate before production"),
    questionary.Choice("dev + tst + acc + prd", value="dev,tst,acc,prd",
                       description="Large enterprise / regulated: test, acceptance, production"),
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _select(question: str, choices: list, yes: bool, default_idx: int = 0) -> str:
    if yes:
        c = choices[default_idx]
        return c.value if isinstance(c, questionary.Choice) else c
    result = questionary.select(question, choices=choices).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    return result


def _checkbox(question: str, choices: list, yes: bool) -> list[str]:
    if yes:
        return [c.value for c in choices if isinstance(c, questionary.Choice) and c.checked]
    result = questionary.checkbox(question, choices=choices).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    return result


def _confirm(question: str, default: bool, yes: bool) -> bool:
    if yes:
        return default
    result = questionary.confirm(question, default=default).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    return result


def _rule(label: str, style: str = "blue") -> None:
    console.rule(f"[bold {style}]{label}[/bold {style}]")


def _print_summary(cfg: ProjectConfig) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    rows: list[tuple[str, str]] = [
        ("Name", cfg.name),
        ("Python", cfg.python_version),
        ("Structure", cfg.structure),
    ]
    if cfg.is_monorepo:
        rows.append(("Apps", ", ".join(cfg.monorepo_apps) or "—"))
    else:
        rows.append(("App type", cfg.app_type))
        rows.append(("API layer", cfg.api_framework))

    rows += [
        ("LLM backend", cfg.llm_backend),
        ("Agent framework", cfg.agent_framework),
        ("Frontend", cfg.frontend),
    ]
    if cfg.frontend_is_nextjs:
        rows.append(("  + Tailwind", "Yes" if cfg.frontend_tailwind else "No"))
        rows.append(("  + shadcn/ui", "Yes" if cfg.frontend_shadcn else "No"))
    rows += [
        ("Database", cfg.database),
        ("Auth", cfg.auth),
        ("Logging", cfg.logging_style),
        ("Docker", "Yes" if cfg.docker else "No"),
        ("Infra", cfg.infra),
        ("Environments", " → ".join(cfg.env_list) if cfg.env_list else "—"),
        ("Pre-commit", "Yes" if cfg.precommit else "No"),
        ("Git init", "Yes" if cfg.git else "No"),
    ]
    for k, v in rows:
        table.add_row(k, v)

    console.print(Panel(table, title=f"[bold green]Creating {cfg.name}[/bold green]", border_style="green"))


# ── main command ──────────────────────────────────────────────────────────────

@app.command()
def main(
    project_name: Optional[str] = typer.Argument(None, help="Project name (prompted if omitted)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept all defaults"),
) -> None:
    """Interactive Python AI/GenAI project scaffolding CLI."""
    console.print(
        Panel(
            "[bold]create-ai-app[/bold] — Python AI/GenAI scaffolding",
            subtitle="[dim]Arrow keys to navigate · Enter to select · Space to toggle checkboxes[/dim]",
            border_style="blue",
        )
    )

    # ── PROJECT ──────────────────────────────────────────────────────────────
    _rule("Project", "blue")

    name = project_name or (
        questionary.text("What is your project called?", default="my-ai-app").ask() or "my-ai-app"
    )

    python_version = _select(
        "Python version?  [dim](uv will install it automatically if not present)[/dim]",
        _PYTHON_VERSIONS, yes,
    )

    structure = _select("Project structure?", _STRUCTURE_TYPES, yes)

    # ── STRUCTURE BRANCH ─────────────────────────────────────────────────────
    if structure == "Monorepo":
        monorepo_apps = _checkbox("Which apps to include?", _MONOREPO_APPS, yes)
        if not monorepo_apps:
            monorepo_apps = ["REST API"]  # guard: at least one
        app_type = "Monorepo"
        api_framework = "FastAPI"  # each app uses its natural default
    else:
        monorepo_apps = []
        app_type = _select("What kind of app?", _SINGLE_APP_TYPES, yes)

        # API layer (hidden for Batch and Teams Bot which have fixed layers)
        if app_type in ("REST API",):
            api_framework = _select("API layer?", _API_FRAMEWORKS["REST API"], yes)
        elif app_type == "Agent":
            api_framework = _select("API / UI layer?", _API_FRAMEWORKS["Agent"], yes)
        elif app_type == "Teams Bot":
            api_framework = "aiohttp"  # always
        else:  # Batch
            api_framework = "None"

    # ── BACKEND ──────────────────────────────────────────────────────────────
    _rule("Backend", "green")

    llm_backend = _select("LLM backend?", _LLM_BACKENDS, yes)

    needs_agent_fw = (
        app_type in ("Agent", "Teams Bot", "Monorepo") or
        (structure == "Monorepo" and any(a in monorepo_apps for a in ("Agent", "Teams Bot")))
    )
    if needs_agent_fw:
        agent_framework = _select("Agent / orchestration framework?", _AGENT_FRAMEWORKS, yes)
    else:
        agent_framework = "None — raw SDK"

    # ── FRONTEND ─────────────────────────────────────────────────────────────
    _rule("Frontend", "cyan")

    # Skip frontend question for Teams Bot and Batch (no meaningful frontend)
    skip_frontend = app_type in ("Teams Bot", "Batch / CronJob")
    if not skip_frontend:
        frontend = _select("Frontend?", _FRONTENDS, yes)
    else:
        frontend = "None"

    frontend_tailwind = False
    frontend_shadcn = False
    if frontend == "Next.js 15":
        frontend_tailwind = _confirm("Include Tailwind CSS?", True, yes)
        if frontend_tailwind:
            frontend_shadcn = _confirm("Include shadcn/ui?", True, yes)

    # ── SERVICES ─────────────────────────────────────────────────────────────
    _rule("Services", "magenta")

    database = _select("Persistence / state?", _DATABASES, yes)

    has_api_layer = api_framework not in ("None", "none", "")
    if has_api_layer:
        auth = _select("API authentication?", _AUTH_OPTIONS, yes)
    else:
        auth = "None"

    # ── LOGGING & DX ─────────────────────────────────────────────────────────
    _rule("Logging & DX", "yellow")

    logging_style = _select("Logging style?", _LOGGING_STYLES, yes)

    precommit = _confirm("Set up pre-commit hooks?  [dim](ruff + check-yaml)[/dim]", True, yes)

    # ── DEVOPS ───────────────────────────────────────────────────────────────
    _rule("DevOps", "red")

    docker = _confirm("Containerize with Docker?", True, yes)

    if docker:
        infra = _select("Cloud deployment target?", _INFRA_OPTIONS, yes)
    else:
        infra = "None"

    if infra != "None":
        environments = _select("Deployment environments?", _ENV_OPTIONS, yes, default_idx=2)
    else:
        environments = "dev"

    git = _confirm("Initialize git repository?", True, yes)

    # ── CONFIRM ──────────────────────────────────────────────────────────────
    cfg = ProjectConfig(
        name=name,
        python_version=python_version,
        structure=structure,
        app_type=app_type,
        monorepo_apps=monorepo_apps,
        llm_backend=llm_backend,
        agent_framework=agent_framework,
        api_framework=api_framework,
        frontend=frontend,
        frontend_tailwind=frontend_tailwind,
        frontend_shadcn=frontend_shadcn,
        database=database,
        auth=auth,
        logging_style=logging_style,
        docker=docker,
        infra=infra,
        environments=environments,
        precommit=precommit,
        git=git,
    )

    console.print()
    _print_summary(cfg)
    console.print()

    if not yes:
        ok = _confirm("Scaffold this project?", True, False)
        if not ok:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    scaffold_project(cfg)
