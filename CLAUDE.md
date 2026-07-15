# CLAUDE.md — create-ai-app

Developer guide for AI-assisted work on this repo.

## Repo overview

Python CLI that scaffolds production-ready AI/GenAI projects. Entry point is `new-ai-app` (installed via `uv tool install .`). Source lives in `src/create_ai_app/`.

## Key architecture decisions

### No Anthropic API key in the CLI
The CLI is a pure scaffolder — no LLM calls, no API key. Intelligence comes from the Claude Code `/new-app` skill (`src/create_ai_app/skills/new-app/SKILL.md`) which runs an interview and writes a context file that the CLI reads via `--context-file`.

### Multi-select app types (not monorepo)
`ProjectConfig.app_types: list[str]` replaces the old `app_type` (single) + `is_monorepo` design. Monorepo was removed — it was a one-client pattern, not a general feature. AKS/Helm were also removed for the same reason.

### Teams Bot + REST API coexistence
When both are selected, `installers/teams.py` writes `router_teams.py` (FastAPI route) and patches `main.py` to include it. It does NOT replace `main.py` with an aiohttp server — that only happens when Teams Bot is selected alone.

### Section re-entry loop
After the summary, the user can edit any of the 6 sections before confirming. Each section function accepts `cur: dict` for pre-filled defaults. `_EDIT_CHOICES` drives the loop in `main()`.

### Skill distribution
`src/create_ai_app/skills/new-app/SKILL.md` is bundled in the package. `new-ai-app install-skill` copies it to `~/.claude/skills/new-app/SKILL.md` using `importlib.resources` (works correctly inside isolated uv tool venvs — file path resolution doesn't).

## Module map

```
src/create_ai_app/
├── cli.py                  # all questions, section functions, --context-file, install-skill
├── models.py               # ProjectConfig dataclass + derived properties
├── scaffold.py             # orchestrates installers, git init, next-steps panel
├── installers/
│   ├── base.py             # always-on: pyproject, config, logging, tests, .env, README
│   ├── api.py              # FastAPI: routes, schemas (uses ai_context for Pydantic fields)
│   ├── agent.py            # agent variants: raw SDK, MAF, LangGraph, AutoGen, LangChain
│   ├── teams.py            # Teams Bot: aiohttp server OR FastAPI router + main.py patch
│   ├── batch.py            # Batch/CronJob: typer CLI, batch runner
│   ├── frontend.py         # Next.js / Streamlit / Chainlit
│   ├── docker.py           # multi-stage Dockerfile
│   ├── infra.py            # Azure Container Apps Bicep / Azure Web App
│   └── logging_.py         # logging variant files
└── skills/
    └── new-app/
        └── SKILL.md        # bundled Claude Code skill
```

## Common patterns

### Adding a new installer option
1. Add the option to the relevant `_section_*` function in `cli.py`
2. Add the field to `ProjectConfig` in `models.py` (with a derived `is_*` property if needed)
3. Wire it into `scaffold.py`
4. Write the installer in `installers/`

### Questionary gotchas
- Do NOT use Rich markup (`[dim]...[/dim]`, `[bold]`, etc.) inside questionary question strings — they render literally. Rich markup only works with `console.print()`.
- Use `questionary.Choice(title, value=..., description=...)` for selects with subtitles.
- Use `questionary.checkbox(...)` for multi-select.

### ai_context flow
`--context-file` loads `recommended_config` (pre-fills section defaults) and `ai_content` (stored in `ProjectConfig.ai_context`). Installers that use it:
- `agent.py`: `agent_names`, `triage_prompt`, `specialist_prompt`, `tools`
- `api.py`: `request_fields`, `response_fields`
- `base.py`: `system_prompt` in generated README

### cosmos_store.py generation
Only generated when `cfg.database == "CosmosDB"`. Do not unconditionally write it.

### Double api.install() guard
In `agent.py`, `api_installer.install()` is only called when `cfg.api_framework == "FastAPI" and not cfg.is_rest_api`. `scaffold.py` handles the REST API case itself.

## Testing after changes

```sh
cd /tmp && new-ai-app test-api --yes          # REST API, all defaults
cd /tmp && new-ai-app test-agent              # interactive: Agent + MAF + CosmosDB
cd /tmp && new-ai-app test-combo              # interactive: REST API + Agent + Teams Bot
```

Check that `uv sync` and `uv run pytest` pass inside the generated project.

## Onboarding (for new contributors)

```sh
git clone git@github.com:luisalmeidabranco/create-ai-app ~/create-ai-app
cd ~/create-ai-app
uv tool install .
new-ai-app install-skill    # wires up /new-app in Claude Code
```

To reinstall after changes:
```sh
uv tool install --reinstall ~/create-ai-app
new-ai-app install-skill
```

## Git workflow

The repo owner runs all git operations. Do not run `git add`, `git commit`, or `git push`.
