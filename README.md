# create-ai-app

Interactive Python AI/GenAI project scaffolding CLI — like `create-t3-app` for Azure OpenAI / Python.

Encodes canonical patterns from production repos so new projects start correct and opinionated rather than blank and risky.

## Quick start

```sh
# Install globally (requires uv)
uv tool install git+https://github.com/luisalmeidabranco/create-ai-app

# Run (interactive)
create-ai-app

# With a project name pre-filled
create-ai-app my-project

# Accept all defaults (REST API + Azure OpenAI + FastAPI + Docker)
create-ai-app my-project --yes
```

> **Don't have uv?** Install it first:
> ```sh
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

## What it scaffolds

### Project types

| Type | What you get |
|---|---|
| **REST API** | FastAPI + gunicorn + Pydantic v2 + auth + health endpoint + multi-stage Dockerfile |
| **Agent** | Tool-calling agent with ContextProviders, memory, MAF / LangGraph / AutoGen / raw SDK variants |
| **Teams Bot** | aiohttp frontdoor for Microsoft Teams, port 3978, `appPackage/` manifest |
| **Batch / CronJob** | typer CLI, batch runner, no web server |
| **Monorepo** | Multiple apps under `apps/`, uv workspace root, shared `deployment/<env>/` |

### Always included

- `uv` + `pyproject.toml` (no pip, no requirements.txt)
- `src/<pkg>/` layout
- `config/config.yaml` + pydantic `BaseSettings` for env
- `configure_logging()` with `LOG_LEVEL` + rotating file handler
- `tests/` with conftest + two stub tests (pytest-asyncio, asyncio_mode=auto)
- `.env.example` with the exact env var names used in production
- `.gitignore` + `.dockerignore`

### Optional

- **LLM backends**: Azure OpenAI (default) · OpenAI.com · Anthropic · Multiple
- **Agent frameworks**: Raw SDK (default) · Microsoft Agent Framework (MAF) · LangGraph · AutoGen · LangChain
- **Database**: CosmosDB · PostgreSQL · SQLite · Redis
- **Auth**: API key header · Azure Entra ID (JWT)
- **Logging**: Console + rotating file · Console only · Structured JSON
- **Frontend**: Next.js 15 + TypeScript → Tailwind? → shadcn/ui? · Streamlit · Chainlit
- **Infra**: Azure Container Apps (Bicep) · AKS (Helm) · Azure Web App
- **Environments**: dev / dev+prd / dev+qa+prd / dev+tst+acc+prd — generates `infra/vars.<env>.sh`
- **Pre-commit**: ruff-check + ruff-format + check-yaml

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

## Requirements

- [uv](https://docs.astral.sh/uv/) — the only hard dependency
- Python 3.11+ (uv will install it if needed)
- git (for `git init` step)
