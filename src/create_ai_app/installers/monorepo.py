from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    """Create the monorepo skeleton: root pyproject.toml workspace, shared/, deployment/."""
    (target / "apps").mkdir(exist_ok=True)

    if "Shared" in cfg.monorepo_apps:
        _write_shared(cfg, target)

    _write_root_pyproject(cfg, target)
    _write_gitignore(target)
    _write_deployment(cfg, target)
    _write_root_readme(cfg, target)


def _write_root_pyproject(cfg: ProjectConfig, target: Path) -> None:
    # Collect workspace members — use "apps/*" to match all app subdirs,
    # or list explicitly if shared lib also present
    members = ['"apps/*"']
    if "Shared" in cfg.monorepo_apps:
        members.append('"shared"')

    members_str = ", ".join(members)

    content = f"""[project]
name = "{cfg.name}"
version = "0.1.0"
description = "{cfg.name} monorepo"
requires-python = ">={cfg.python_version}"

# This root pyproject.toml defines the uv workspace.
# Each app under apps/ has its own pyproject.toml with its own deps.
# Run `uv sync` from the repo root to install all workspaces.

[tool.uv.workspace]
members = [{members_str}]

[dependency-groups]
dev = [
    "ruff>=0.8.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
"""
    (target / "pyproject.toml").write_text(content)


def _write_gitignore(target: Path) -> None:
    content = """# Python
__pycache__/
*.py[cod]
*.so
build/
dist/
*.egg-info/

# Virtual environments
.venv/
venv/

# Secrets
.env
.env.*
!.env.example

# Tooling
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# IDEs
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Azure
.azure-context/
.azure/

# Node
node_modules/
.next/

# Claude Code
CLAUDE.md
**/CLAUDE.md
.claude/
"""
    (target / ".gitignore").write_text(content)


def _write_shared(cfg: ProjectConfig, target: Path) -> None:
    shared = target / "shared"
    pkg_name = f"{cfg.pkg_name}_shared"
    pkg = shared / "src" / pkg_name
    pkg.mkdir(parents=True, exist_ok=True)

    (shared / "pyproject.toml").write_text(f"""[project]
name = "{cfg.name}-shared"
version = "0.1.0"
description = "Shared utilities for {cfg.name}"
requires-python = ">={cfg.python_version}"
dependencies = [
    "pydantic>=2.9.0",
    "pyyaml>=6.0.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg_name}"]
""")

    (pkg / "__init__.py").write_text(f'__version__ = "0.1.0"\n')
    (pkg / "types.py").write_text("""from __future__ import annotations
from pydantic import BaseModel


class AgentRequest(BaseModel):
    message: str
    session_id: str = "default"
    context: dict = {}


class AgentResponse(BaseModel):
    reply: str
    metadata: dict = {}
""")
    (pkg / "utils.py").write_text("""from __future__ import annotations
from pathlib import Path
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}
""")


def _write_deployment(cfg: ProjectConfig, target: Path) -> None:
    deployment = target / "deployment"
    deployment.mkdir(exist_ok=True)

    for env in cfg.env_list:
        env_dir = deployment / env
        env_dir.mkdir(exist_ok=True)
        (env_dir / "vars.sh").write_text(f"""#!/usr/bin/env bash
# Deployment variables for: {env}

APP_NAME="{cfg.name}"
ENV="{env}"
LOCATION="westeurope"
RESOURCE_GROUP="${{APP_NAME}}-${{ENV}}-rg"
REGISTRY_NAME=""   # Azure Container Registry (no .azurecr.io)
IMAGE_TAG="latest"
""")

    (deployment / "README.md").write_text(f"""# Deployment

Each subdirectory contains environment-specific variables.

## Environments
{chr(10).join(f"- `{e}/vars.sh` — {e} environment" for e in cfg.env_list)}

## Usage

```bash
source deployment/dev/vars.sh
# then run your deploy script
```
""")


def _write_root_readme(cfg: ProjectConfig, target: Path) -> None:
    apps_list = "\n".join(
        f"- `apps/{_app_dir(a)}/` — {a}" for a in cfg.monorepo_apps if a != "Shared"
    )
    if "Shared" in cfg.monorepo_apps:
        apps_list += "\n- `shared/` — Shared library"

    content = f"""# {cfg.name}

Python AI/GenAI monorepo.

## Apps

{apps_list}

## Getting started

```bash
uv sync          # installs all workspace packages
uv run pytest    # run all tests
```

## Deployment

See `deployment/` for per-environment variables.
"""
    (target / "README.md").write_text(content)


def _app_dir(app_name: str) -> str:
    return {
        "REST API": "api",
        "Agent": "agent",
        "Teams Bot": "teams-frontdoor",
        "Batch": "pipeline",
        "Shared": "shared",
    }.get(app_name, app_name.lower().replace(" ", "-"))
