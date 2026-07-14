from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    _write_dockerfile(cfg, target)
    _write_dockerignore(target)


def _write_dockerfile(cfg: ProjectConfig, target: Path) -> None:
    copy_paths = "COPY main.py gunicorn.conf.py ./"
    if cfg.is_batch:
        copy_paths = "COPY src/ ./src/"
    elif cfg.is_agent and cfg.api_framework in ("Chainlit", "Streamlit"):
        copy_paths = "COPY main.py ./"
    else:
        copy_paths = "COPY main.py gunicorn.conf.py ./"

    cmd = "gunicorn"
    if cfg.is_batch:
        cmd = f'python -m {cfg.pkg_name}.cli'
    elif cfg.api_framework == "Chainlit":
        cmd = "chainlit run main.py --host 0.0.0.0 --port 3100"
    elif cfg.api_framework == "Streamlit":
        cmd = "streamlit run main.py --server.port 3100 --server.address 0.0.0.0"

    if cmd == "gunicorn":
        cmd_line = 'CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]'
    else:
        cmd_line = f'CMD {cmd.split()}'
        cmd_line = 'CMD [' + ', '.join(f'"{p}"' for p in cmd.split()) + ']'

    content = f"""# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder: resolve locked dependencies into a self-contained venv.
# ---------------------------------------------------------------------------
FROM python:{cfg.python_version}-slim AS builder

ENV UV_PYTHON_DOWNLOADS=0 \\
    UV_LINK_MODE=copy \\
    UV_PROJECT_ENVIRONMENT=/opt/venv \\
    PIP_NO_CACHE_DIR=1

RUN pip install "uv==0.5.29"

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

# ---------------------------------------------------------------------------
# Runtime: slim base, non-root user, the venv, and the app.
# ---------------------------------------------------------------------------
FROM python:{cfg.python_version}-slim AS runtime

RUN apt-get update \\
    && apt-get install -y --no-install-recommends curl \\
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PATH="/opt/venv/bin:$PATH"

WORKDIR /code

COPY --from=builder /opt/venv /opt/venv

{copy_paths}
COPY src/ ./src/
COPY config/ ./config/

USER app

EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
    CMD curl -fsS http://localhost:3100/health || exit 1

{cmd_line}
"""
    (target / "Dockerfile").write_text(content)


def _write_dockerignore(target: Path) -> None:
    content = """.git
.gitignore
.venv
__pycache__/
*.pyc
*.pyo

# not part of the image
tests/
infra/
scripts/
.github/

# caches / tooling
.pytest_cache/
.mypy_cache/
.ruff_cache/
.ipynb_checkpoints/
dist/
build/

# env files
.env
.env.*
!.env.example

# logs
*.log
logs/
"""
    (target / ".dockerignore").write_text(content)
