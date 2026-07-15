from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from create_ai_app.models import ProjectConfig
from create_ai_app.scaffold import scaffold_project

app = typer.Typer(
    name="new-ai-app",
    help="Interactive Python AI/GenAI project scaffolding CLI",
    add_completion=False,
)

console = Console()

# ── option lists ──────────────────────────────────────────────────────────────

_PYTHON_VERSIONS = [
    questionary.Choice("3.13  (recommended)", value="3.13"),
    questionary.Choice("3.12", value="3.12"),
    questionary.Choice("3.11", value="3.11"),
]

_APP_TYPES = [
    questionary.Choice("REST API", value="REST API", checked=True,
                       description="FastAPI backend with health endpoint, auth, and LLM service"),
    questionary.Choice("Agent", value="Agent", checked=False,
                       description="Conversational agent with tool-calling, memory, and context providers"),
    questionary.Choice("Teams Bot", value="Teams Bot", checked=False,
                       description="Microsoft Teams bot frontdoor — aiohttp adapter, port 3978"),
    questionary.Choice("Batch / CronJob", value="Batch / CronJob", checked=False,
                       description="Script or scheduled job that processes data without a web server"),
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

_API_FRAMEWORKS_REST = [
    questionary.Choice("FastAPI  (recommended)", value="FastAPI",
                       description="Async, Pydantic v2, automatic OpenAPI docs"),
    questionary.Choice("Flask", value="Flask",
                       description="Sync WSGI — simpler but no async"),
    questionary.Choice("None", value="None",
                       description="No web layer — library or background service"),
]

_API_FRAMEWORKS_AGENT = [
    questionary.Choice("Chainlit  (recommended)", value="Chainlit",
                       description="Chat UI framework built for LLM agents"),
    questionary.Choice("FastAPI + SSE", value="FastAPI",
                       description="Streaming API for custom frontends"),
    questionary.Choice("Streamlit", value="Streamlit",
                       description="Quick internal UI — no separate frontend project"),
    questionary.Choice("None", value="None",
                       description="Agent library only — integrate into your own entry point"),
]

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
    questionary.Choice("Console + rotating file  (recommended)", value="rotating",
                       description="Logs to stdout and writes rotating app.log. Good for containers and VMs."),
    questionary.Choice("Console only (simple)", value="basic",
                       description="Single-line basicConfig. Good for scripts and local dev."),
    questionary.Choice("Structured JSON", value="json",
                       description="Machine-readable JSON lines. Best for Application Insights / log aggregation."),
]

_INFRA_OPTIONS = [
    questionary.Choice("Azure Container Apps — Bicep  (recommended)", value="Azure Container Apps — Bicep",
                       description="Serverless containers on ACA — matches bpo_email_int, alex-hr pattern"),
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

_EDIT_CHOICES = [
    questionary.Choice("✓  Create project", value="create"),
    questionary.Choice("   Edit Project", value="project"),
    questionary.Choice("   Edit Backend", value="backend"),
    questionary.Choice("   Edit Frontend", value="frontend"),
    questionary.Choice("   Edit Services", value="services"),
    questionary.Choice("   Edit Logging & DX", value="logging"),
    questionary.Choice("   Edit DevOps", value="devops"),
    questionary.Choice("✕  Cancel", value="cancel"),
]


# ── primitive helpers ─────────────────────────────────────────────────────────

def _select(question: str, choices: list, yes: bool, default_idx: int = 0,
            current_value: str | None = None) -> str:
    if current_value is not None:
        for i, c in enumerate(choices):
            if (c.value if isinstance(c, questionary.Choice) else c) == current_value:
                default_idx = i
                break
    if yes:
        c = choices[default_idx]
        return c.value if isinstance(c, questionary.Choice) else c
    default = choices[default_idx]
    default_val = default.value if isinstance(default, questionary.Choice) else default
    result = questionary.select(question, choices=choices, default=default_val).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    return result


def _checkbox(question: str, choices: list, yes: bool,
              current_values: list | None = None) -> list[str]:
    if current_values is not None:
        for c in choices:
            if isinstance(c, questionary.Choice):
                c.checked = c.value in current_values
    if yes:
        return [c.value for c in choices if isinstance(c, questionary.Choice) and c.checked]
    result = questionary.checkbox(question, choices=choices).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    if not result:
        console.print("\n[yellow]Nothing selected — defaulting to REST API.[/yellow]")
        return ["REST API"]
    return result


def _confirm(question: str, default: bool, yes: bool,
             current_value: bool | None = None) -> bool:
    effective_default = current_value if current_value is not None else default
    if yes:
        return effective_default
    result = questionary.confirm(question, default=effective_default).ask()
    if result is None:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    return result


def _rule(label: str, style: str = "blue") -> None:
    console.rule(f"[bold {style}]{label}[/bold {style}]")


# ── context file ─────────────────────────────────────────────────────────────

def _load_context_file(path: str) -> tuple[dict, dict | None]:
    """Load a Claude Code-generated context file.

    Expected shape:
      {
        "suggested_name": "kebab-case",          # optional
        "recommended_config": { ... },            # ProjectConfig field overrides
        "ai_content": { prompts, tools, schemas } # passed to installers
      }
    """
    try:
        data = json.loads(Path(path).read_text())
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow]  Could not load context file: {e}")
        return {}, None

    recommended = dict(data.get("recommended_config") or {})
    if "suggested_name" in data:
        recommended.setdefault("name", data["suggested_name"])

    ai_content = data.get("ai_content") or None

    if ai_content:
        agents = " + ".join(ai_content.get("agent_names") or [])
        tools = ", ".join(t["name"] for t in ai_content.get("tools") or [])
        req = ", ".join(f["name"] for f in ai_content.get("request_fields") or [])
        resp = ", ".join(f["name"] for f in ai_content.get("response_fields") or [])
        console.rule("[bold purple]AI Context[/bold purple]")
        if agents:
            console.print(f"  [dim]Agents:[/dim]  {agents}")
        if tools:
            console.print(f"  [dim]Tools:[/dim]   {tools}")
        if req or resp:
            console.print(f"  [dim]Schema:[/dim]  ({req}) → ({resp})")

    return recommended, ai_content


# ── section functions ─────────────────────────────────────────────────────────

def _section_project(yes: bool, cur: dict, ai_ctx: dict | None) -> dict:
    _rule("Project", "blue")

    default_name = (ai_ctx or {}).get("suggested_name") or cur.get("name", "my-ai-app")
    if yes:
        name = cur.get("name", default_name)
    else:
        name = questionary.text("What is your project called?", default=default_name).ask() or default_name

    python_version = _select(
        "Python version?  (uv will install it automatically if not present)",
        _PYTHON_VERSIONS, yes, current_value=cur.get("python_version"),
    )

    app_types = _checkbox(
        "What kind of app?  (space to select multiple)",
        _APP_TYPES, yes, current_values=cur.get("app_types"),
    )

    if "REST API" in app_types:
        cur_fw = cur.get("api_framework") if cur.get("api_framework") in [
            c.value for c in _API_FRAMEWORKS_REST] else None
        api_framework = _select("API layer?", _API_FRAMEWORKS_REST, yes, current_value=cur_fw)
    elif "Agent" in app_types and "Teams Bot" not in app_types:
        cur_fw = cur.get("api_framework") if cur.get("api_framework") in [
            c.value for c in _API_FRAMEWORKS_AGENT] else None
        api_framework = _select("API / UI layer?", _API_FRAMEWORKS_AGENT, yes, current_value=cur_fw)
    elif "Teams Bot" in app_types:
        api_framework = "aiohttp"
    else:
        api_framework = "None"

    return {
        "name": name,
        "python_version": python_version,
        "app_types": app_types,
        "api_framework": api_framework,
    }


def _section_backend(yes: bool, cur: dict) -> dict:
    _rule("Backend", "green")

    llm_backend = _select("LLM backend?", _LLM_BACKENDS, yes,
                          current_value=cur.get("llm_backend"))

    app_types = cur.get("app_types", ["REST API"])
    needs_agent_fw = "Agent" in app_types or "Teams Bot" in app_types
    if needs_agent_fw:
        agent_framework = _select("Agent / orchestration framework?", _AGENT_FRAMEWORKS, yes,
                                  current_value=cur.get("agent_framework"))
    else:
        agent_framework = "None — raw SDK"

    return {"llm_backend": llm_backend, "agent_framework": agent_framework}


def _section_frontend(yes: bool, cur: dict) -> dict:
    _rule("Frontend", "cyan")

    app_types = cur.get("app_types", ["REST API"])
    skip = set(app_types) <= {"Teams Bot", "Batch / CronJob"}
    if skip:
        return {"frontend": "None", "frontend_tailwind": False, "frontend_shadcn": False}

    frontend = _select("Frontend?", _FRONTENDS, yes, current_value=cur.get("frontend"))

    frontend_tailwind = False
    frontend_shadcn = False
    if frontend == "Next.js 15":
        frontend_tailwind = _confirm("Include Tailwind CSS?", True, yes,
                                     current_value=cur.get("frontend_tailwind"))
        if frontend_tailwind:
            frontend_shadcn = _confirm("Include shadcn/ui?", True, yes,
                                       current_value=cur.get("frontend_shadcn"))

    return {
        "frontend": frontend,
        "frontend_tailwind": frontend_tailwind,
        "frontend_shadcn": frontend_shadcn,
    }


def _section_services(yes: bool, cur: dict) -> dict:
    _rule("Services", "magenta")

    database = _select("Persistence / state?", _DATABASES, yes,
                       current_value=cur.get("database"))

    api_framework = cur.get("api_framework", "FastAPI")
    has_api_layer = api_framework not in ("None", "none", "")
    if has_api_layer:
        auth = _select("API authentication?", _AUTH_OPTIONS, yes,
                       current_value=cur.get("auth"))
    else:
        auth = "None"

    return {"database": database, "auth": auth}


def _section_logging_dx(yes: bool, cur: dict) -> dict:
    _rule("Logging & DX", "yellow")

    logging_style = _select("Logging style?", _LOGGING_STYLES, yes,
                            current_value=cur.get("logging_style"))
    precommit = _confirm("Set up pre-commit hooks?  (ruff + check-yaml)", True, yes,
                         current_value=cur.get("precommit"))

    return {"logging_style": logging_style, "precommit": precommit}


def _section_devops(yes: bool, cur: dict) -> dict:
    _rule("DevOps", "red")

    docker = _confirm("Containerize with Docker?", True, yes,
                      current_value=cur.get("docker"))

    if docker:
        infra = _select("Cloud deployment target?", _INFRA_OPTIONS, yes,
                        current_value=cur.get("infra"))
    else:
        infra = "None"

    if infra != "None":
        environments = _select("Deployment environments?", _ENV_OPTIONS, yes,
                               default_idx=2, current_value=cur.get("environments"))
    else:
        environments = "dev"

    git = _confirm("Initialize git repository?", True, yes,
                   current_value=cur.get("git"))

    return {"docker": docker, "infra": infra, "environments": environments, "git": git}


# ── summary ───────────────────────────────────────────────────────────────────

def _build_config(state: dict, ai_ctx: dict | None) -> ProjectConfig:
    return ProjectConfig(
        name=state["name"],
        python_version=state["python_version"],
        app_types=state["app_types"],
        api_framework=state["api_framework"],
        llm_backend=state["llm_backend"],
        agent_framework=state["agent_framework"],
        frontend=state["frontend"],
        frontend_tailwind=state["frontend_tailwind"],
        frontend_shadcn=state["frontend_shadcn"],
        database=state["database"],
        auth=state["auth"],
        logging_style=state["logging_style"],
        precommit=state["precommit"],
        docker=state["docker"],
        infra=state["infra"],
        environments=state["environments"],
        git=state["git"],
        ai_context=ai_ctx,
    )


def _print_summary(cfg: ProjectConfig, ai_ctx: dict | None) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    if ai_ctx:
        table.add_row("AI context", f"[green]✓[/green] {ai_ctx.get('suggested_name', 'generated')}")

    rows: list[tuple[str, str]] = [
        ("Name", cfg.name),
        ("Python", cfg.python_version),
        ("App type", ", ".join(cfg.app_types)),
        ("API layer", cfg.api_framework),
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

    console.print(Panel(table, title=f"[bold green]Creating {cfg.name}[/bold green]",
                        border_style="green"))


# ── main ──────────────────────────────────────────────────────────────────────

@app.command("install-skill")
def install_skill() -> None:
    """Install the /new-app Claude Code skill into ~/.claude/skills/."""
    import importlib.resources

    skill_dst = Path.home() / ".claude" / "skills" / "new-app"
    skill_dst.mkdir(parents=True, exist_ok=True)

    skill_file = importlib.resources.files("create_ai_app").joinpath("skills/new-app/SKILL.md")
    content = skill_file.read_text(encoding="utf-8")
    (skill_dst / "SKILL.md").write_text(content, encoding="utf-8")

    console.print(f"[green]✓[/green] Skill installed: [bold]/new-app[/bold]")
    console.print(f"  [dim]{skill_dst / 'SKILL.md'}[/dim]")
    console.print("  Re-run after [bold]uv tool install --reinstall .[/bold] to pick up skill updates.")


@app.command()
def main(
    project_name: Optional[str] = typer.Argument(None, help="Project name (prompted if omitted)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept all defaults"),
    context_file: Optional[str] = typer.Option(None, "--context-file", "-c",
                                                help="Path to Claude Code-generated context JSON"),
) -> None:
    """Interactive Python AI/GenAI project scaffolding CLI."""
    console.print(Panel(
        "[bold]new-ai-app[/bold] — Python AI/GenAI scaffolding",
        subtitle="[dim]Arrow keys to navigate · Enter to select · Space to toggle checkboxes[/dim]",
        border_style="blue",
    ))

    # Load Claude Code-generated context if provided
    ai_ctx: dict | None = None
    state: dict = {}
    if context_file:
        recommended, ai_ctx = _load_context_file(context_file)
        state.update(recommended)  # pre-populates defaults for all sections

    if project_name:
        state["name"] = project_name

    state.update(_section_project(yes, state, ai_ctx))
    state.update(_section_backend(yes, state))
    state.update(_section_frontend(yes, state))
    state.update(_section_services(yes, state))
    state.update(_section_logging_dx(yes, state))
    state.update(_section_devops(yes, state))

    # Confirm / re-entry loop
    while True:
        cfg = _build_config(state, ai_ctx)
        console.print()
        _print_summary(cfg, ai_ctx)
        console.print()

        if yes:
            break

        action = questionary.select("", choices=_EDIT_CHOICES).ask()
        if action is None or action == "cancel":
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)
        if action == "create":
            break

        _SECTION_FNS = {
            "project": lambda: state.update(_section_project(False, state, ai_ctx)),
            "backend": lambda: state.update(_section_backend(False, state)),
            "frontend": lambda: state.update(_section_frontend(False, state)),
            "services": lambda: state.update(_section_services(False, state)),
            "logging": lambda: state.update(_section_logging_dx(False, state)),
            "devops": lambda: state.update(_section_devops(False, state)),
        }
        if action in _SECTION_FNS:
            _SECTION_FNS[action]()

    scaffold_project(cfg)
