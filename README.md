# create-ai-app

Interactive Python AI/GenAI project scaffolding CLI — like `create-t3-app` for Azure OpenAI / Python.

Encodes canonical patterns from production repos so new projects start correct and opinionated rather than blank and risky.

## Setup (new team member)

```sh
# 1. install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. clone and install
git clone git@github.com:luisalmeidabranco/create-ai-app ~/create-ai-app
cd ~/create-ai-app
uv tool install .

# 3. wire up the Claude Code skill
new-ai-app install-skill
```

That's it. The `/new-app` skill is now available in Claude Code.

## Usage

**Via Claude Code (recommended):**
Type `/new-app` — Claude will interview you about your use case, generate a context file with domain-specific prompts/tools/schemas, then launch the CLI with intelligent defaults pre-selected.

**Direct CLI:**
```sh
new-ai-app                        # interactive
new-ai-app my-project             # name pre-filled
new-ai-app my-project --yes       # accept all defaults
```

## Keeping up to date

```sh
git -C ~/create-ai-app pull
uv tool install --reinstall ~/create-ai-app
new-ai-app install-skill          # picks up skill updates
```

## What it scaffolds

### Project types (multi-select)

| Type | What you get |
|---|---|
| **REST API** | FastAPI + gunicorn + Pydantic v2 + auth + health endpoint + multi-stage Dockerfile |
| **Agent** | Tool-calling agent with ContextProviders, memory, MAF / LangGraph / AutoGen / raw SDK variants |
| **Teams Bot** | Microsoft Teams frontdoor — aiohttp adapter or FastAPI route, port 3978, `appPackage/` manifest |
| **Batch / CronJob** | typer CLI, batch runner, no web server |

Combine types freely — REST API + Agent wires the agent into the FastAPI routes; Teams Bot alongside REST API adds `/api/messages` to the existing app.

### Always included

- `uv` + `pyproject.toml` (no pip, no requirements.txt)
- `src/<pkg>/` layout
- `config/config.yaml` + pydantic `BaseSettings` for env
- `configure_logging()` with `LOG_LEVEL` + rotating file handler
- `tests/` with conftest + stub tests (pytest-asyncio, asyncio_mode=auto)
- `README.md` with getting started steps
- `.env.example` with the exact env var names the code reads
- `.gitignore` + `.dockerignore`

### Optional

- **LLM backends**: Azure OpenAI (default) · OpenAI.com · Anthropic · Multiple
- **Agent frameworks**: Raw SDK (default) · Microsoft Agent Framework (MAF) · LangGraph · AutoGen · LangChain
- **Database**: CosmosDB · PostgreSQL · SQLite · Redis
- **Auth**: API key header · Azure Entra ID (JWT)
- **Logging**: Console + rotating file · Console only · Structured JSON
- **Frontend**: Next.js 15 + TypeScript → Tailwind? → shadcn/ui? · Streamlit · Chainlit
- **Infra**: Azure Container Apps (Bicep) · Azure Web App
- **Environments**: dev / dev+prd / dev+qa+prd / dev+tst+acc+prd

## Mistakes this prevents

| Without | With |
|---|---|
| `requirements.txt` + pip | `uv` + `pyproject.toml` |
| Root-level spaghetti | `src/<pkg>/` enforced |
| Hardcoded API key | `.env.example` + APP_API_KEY pattern |
| No auth on API | APP_API_KEY header check wired in |
| `FROM python:3.12` (bloated, root) | Multi-stage slim + non-root + HEALTHCHECK |
| No `/health` endpoint | Health route + Dockerfile HEALTHCHECK |
| `print()` for logging | `configure_logging()` + LOG_LEVEL env var |
| Choosing LangChain by default | Forces explicit decision; raw SDK is the default |
| Single environment | Per-env `infra/vars.<env>.sh` files generated |
| Generic "example_tool" stubs | Domain-specific tools from the `/new-app` interview |
