from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig
from create_ai_app.installers._utils import copy_template, render_template


def install(cfg: ProjectConfig, target: Path) -> None:
    _write_pyproject(cfg, target)
    _write_gitignore(target)
    _write_env_example(cfg, target)
    _write_python_version(cfg, target)
    _write_config_yaml(cfg, target)
    _write_src_skeleton(cfg, target)
    _write_tests_skeleton(cfg, target)
    if cfg.infra != "None":
        _write_infra_vars(cfg, target)


def _write_pyproject(cfg: ProjectConfig, target: Path) -> None:
    llm_deps = {
        "Azure OpenAI": '    "openai>=1.57.0",',
        "OpenAI.com": '    "openai>=1.57.0",',
        "Anthropic": '    "anthropic>=0.40.0",',
        "Multiple": '    "openai>=1.57.0",\n    "anthropic>=0.40.0",',
    }
    llm_dep = llm_deps.get(cfg.llm_backend, '    "openai>=1.57.0",')

    api_deps = ""
    if cfg.api_framework == "FastAPI":
        api_deps = '    "fastapi>=0.115.0",\n    "uvicorn>=0.32.0",\n    "gunicorn>=23.0.0",\n    "python-multipart>=0.0.9",'
    elif cfg.api_framework == "Flask":
        api_deps = '    "flask>=3.1.0",\n    "gunicorn>=23.0.0",'
    elif cfg.api_framework == "Chainlit":
        api_deps = '    "chainlit>=2.0.0",'
    elif cfg.api_framework == "Streamlit":
        api_deps = '    "streamlit>=1.40.0",'

    db_deps = ""
    if cfg.database == "PostgreSQL":
        db_deps = '    "asyncpg>=0.30.0",\n    "sqlalchemy>=2.0.0",'
    elif cfg.database == "CosmosDB":
        db_deps = '    "azure-cosmos>=4.9.0",'
    elif cfg.database == "Redis":
        db_deps = '    "redis>=5.2.0",'

    agent_deps = ""
    if cfg.agent_framework == "LangGraph":
        agent_deps = '    "langgraph>=0.2.0",\n    "langchain-openai>=0.2.0",'
    elif cfg.agent_framework == "AutoGen":
        agent_deps = '    "pyautogen>=0.4.0",'
    elif cfg.agent_framework == "LangChain":
        agent_deps = '    "langchain>=0.3.0",\n    "langchain-openai>=0.2.0",'
    elif cfg.agent_framework == "Microsoft AF":
        agent_deps = (
            '    "agent-framework-core>=1.11.0",\n'
            '    "agent-framework-openai>=1.10.1",\n'
            '    "agent-framework-orchestrations>=1.0.0",\n'
            '    "azure-identity>=1.19.0",'
        )

    teams_deps = ""
    if cfg.is_teams:
        teams_deps = '    "aiohttp>=3.11.0",\n    "microsoft-agents-hosting-aiohttp>=1.0.0b1",'

    all_extra = "\n".join(
        d for d in [llm_dep, api_deps, db_deps, agent_deps, teams_deps] if d
    )

    content = f"""[project]
name = "{cfg.name}"
version = "0.1.0"
description = "Add your description here"
requires-python = ">={cfg.python_version}"
dependencies = [
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.1",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
{all_extra}
]

[dependency-groups]
dev = [
    "ruff>=0.8.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{cfg.pkg_name}"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
"""
    (target / "pyproject.toml").write_text(content)


def _write_gitignore(target: Path) -> None:
    content = """# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/
.eggs/

# Virtual environments
.venv/
venv/
env/

# Environment / secrets
.env
.env.*
!.env.example

# Tooling caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.ipynb_checkpoints/

# Coverage
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

# Azure context (repo-local, may contain subscription IDs)
.azure-context/
.azure/

# Claude Code
CLAUDE.md
**/CLAUDE.md
.claude/
"""
    (target / ".gitignore").write_text(content)


def _write_env_example(cfg: ProjectConfig, target: Path) -> None:
    azure_block = ""
    if cfg.uses_azure_openai:
        azure_block = """
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-12-01-preview
"""
    elif cfg.llm_backend == "OpenAI.com":
        azure_block = "\n# OpenAI\nOPENAI_API_KEY=\n"
    elif cfg.llm_backend == "Anthropic":
        azure_block = "\n# Anthropic\nANTHROPIC_API_KEY=\n"
    elif cfg.llm_backend == "Multiple":
        azure_block = """
# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# OpenAI (fallback)
OPENAI_API_KEY=

# Anthropic (fallback)
ANTHROPIC_API_KEY=
"""

    auth_block = ""
    if cfg.auth == "API key header":
        auth_block = """
# API authentication
APP_API_KEY=your-secret-key-here
APP_API_KEY_HEADER=X-API-Key
"""

    logging_block = """
# Logging
LOG_LEVEL=INFO
LOCAL_LOG_DIR=logs
"""

    content = f"""# {cfg.name} — environment configuration
# Copy to .env and fill in your values. Never commit .env.
{azure_block}{auth_block}{logging_block}"""
    (target / ".env.example").write_text(content)


def _write_python_version(cfg: ProjectConfig, target: Path) -> None:
    (target / ".python-version").write_text(f"{cfg.python_version}\n")


def _write_config_yaml(cfg: ProjectConfig, target: Path) -> None:
    (target / "config").mkdir(exist_ok=True)
    content = """llm:
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 4096

app:
  log_level: INFO
"""
    (target / "config" / "config.yaml").write_text(content)


def _write_src_skeleton(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(f'__version__ = "0.1.0"\n')

    _write_config_module(cfg, pkg)
    _write_logging_config(pkg)

    resources = pkg / "resources" / "prompts"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "system_prompt.md").write_text(
        f"# System Prompt\n\nYou are a helpful AI assistant for {cfg.name}.\n"
    )


def _write_config_module(cfg: ProjectConfig, pkg: Path) -> None:
    azure_fields = ""
    if cfg.uses_azure_openai:
        azure_fields = """
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
"""
    elif cfg.llm_backend == "OpenAI.com":
        azure_fields = '\n    openai_api_key: str = ""\n'
    elif cfg.llm_backend == "Anthropic":
        azure_fields = '\n    anthropic_api_key: str = ""\n'

    auth_field = ""
    if cfg.auth == "API key header":
        auth_field = """
    app_api_key: str = ""
    app_api_key_header: str = "X-API-Key"
"""

    content = f"""from __future__ import annotations

import yaml
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
{azure_fields}{auth_field}
    log_level: str = "INFO"
    local_log_dir: str = "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_config(path: str = "config/config.yaml") -> dict:
    with open(Path(path)) as f:
        return yaml.safe_load(f)
"""
    (pkg / "config.py").write_text(content)


def _write_logging_config(pkg: Path) -> None:
    content = '''from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _resolve_level(raw: str | None) -> int:
    level = logging.getLevelName((raw or "INFO").strip().upper())
    return level if isinstance(level, int) else logging.INFO


def configure_logging() -> None:
    """Configure root logging from LOG_LEVEL / LOCAL_LOG_DIR. Idempotent."""
    global _CONFIGURED

    level = _resolve_level(os.getenv("LOG_LEVEL"))
    root = logging.getLogger()
    root.setLevel(level)

    if _CONFIGURED:
        for h in root.handlers:
            h.setLevel(level)
        return

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_dir = (os.getenv("LOCAL_LOG_DIR") or "").strip()
    if log_dir:
        try:
            path = Path(log_dir)
            path.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                path / "app.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except OSError as e:
            root.warning("Could not set up file logging in %r: %s", log_dir, e)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error", "gunicorn.access"):
        logging.getLogger(name).setLevel(level)

    _CONFIGURED = True
'''
    (pkg / "logging_config.py").write_text(content)


def _write_infra_vars(cfg: ProjectConfig, target: Path) -> None:
    infra_dir = target / "infra"
    infra_dir.mkdir(exist_ok=True)

    common_content = f"""#!/usr/bin/env bash
# Common variables shared across all environments.
# Source this file from a vars.<env>.sh before deploying.

APP_NAME="{cfg.name}"
LOCATION="westeurope"
REGISTRY_NAME=""   # Azure Container Registry name (no .azurecr.io)
IMAGE_TAG="latest"
"""
    (infra_dir / "vars.common.sh").write_text(common_content)

    for env in cfg.env_list:
        env_content = f"""#!/usr/bin/env bash
# Environment: {env}
source "$(dirname "$0")/vars.common.sh"

ENV="{env}"
RESOURCE_GROUP="${{APP_NAME}}-${{ENV}}-rg"
CONTAINER_APP_NAME="${{APP_NAME}}-${{ENV}}"

# Override per-env values below:
# LOCATION="germanywestcentral"
"""
        (infra_dir / f"vars.{env}.sh").write_text(env_content)

    example_content = """#!/usr/bin/env bash
# Copy to vars.dev.sh / vars.prd.sh and fill in your values.
source "$(dirname "$0")/vars.common.sh"

ENV="dev"
RESOURCE_GROUP="${APP_NAME}-${ENV}-rg"
CONTAINER_APP_NAME="${APP_NAME}-${ENV}"
"""
    (infra_dir / "vars.example.sh").write_text(example_content)


def _write_tests_skeleton(cfg: ProjectConfig, target: Path) -> None:
    tests = target / "tests"
    tests.mkdir(exist_ok=True)

    (tests / "__init__.py").write_text("")

    (tests / "conftest.py").write_text(f"""import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "mocked response"
    client.chat.completions.create.return_value = response
    return client
""")
