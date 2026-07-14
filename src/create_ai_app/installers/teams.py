from __future__ import annotations

import json
from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    """Install Teams Bot files — base files already written by scaffold.py."""
    _write_main(cfg, target)
    _write_bot(cfg, target)
    _write_app_package(cfg, target)
    _add_teams_env(target)
    _write_dockerfile(cfg, target)
    _write_tests(cfg, target)


def _write_main(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    pkg.mkdir(parents=True, exist_ok=True)

    (target / "main.py").write_text(f"""from __future__ import annotations
import logging
from aiohttp import web

from src.{cfg.pkg_name}.app import create_app
from src.{cfg.pkg_name}.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=3978)
""")


def _write_bot(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name

    (pkg / "bot.py").write_text(f"""from __future__ import annotations
import logging
from aiohttp import web
from aiohttp.web import Request, Response

logger = logging.getLogger(__name__)

# Microsoft Teams sends activities to this path.
MESSAGES_PATH = "/api/messages"


async def handle_messages(request: Request) -> Response:
    \"\"\"Entry point for all Teams Bot Framework activities.\"\"\"
    if request.content_type != "application/json":
        return Response(status=415)

    body = await request.json()
    activity_type = body.get("type", "")
    logger.debug("Received activity: type=%s", activity_type)

    if activity_type == "message":
        text = body.get("text", "")
        logger.info("Message received: %s", text[:100])
        # TODO: call your agent/backend here and send a reply via Bot Framework
        reply = {{"type": "message", "text": f"Echo: {{text}}"}}
        return web.json_response(reply)

    return Response(status=200)
""")

    (pkg / "app.py").write_text(f"""from __future__ import annotations
from aiohttp import web
from src.{cfg.pkg_name}.bot import handle_messages, MESSAGES_PATH


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post(MESSAGES_PATH, handle_messages)
    app.router.add_get("/health", lambda r: web.json_response({{"status": "ok"}}))
    return app
""")


def _write_app_package(cfg: ProjectConfig, target: Path) -> None:
    app_pkg = target / "appPackage"
    app_pkg.mkdir(exist_ok=True)

    manifest = {
        "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
        "manifestVersion": "1.16",
        "version": "1.0.0",
        "id": "${{TEAMS_APP_ID}}",
        "packageName": f"com.{cfg.pkg_name}",
        "developer": {
            "name": "Your Company",
            "websiteUrl": "https://example.com",
            "privacyUrl": "https://example.com/privacy",
            "termsOfUseUrl": "https://example.com/terms",
        },
        "name": {"short": cfg.name, "full": cfg.name},
        "description": {"short": f"{cfg.name} Teams Bot", "full": f"{cfg.name} Microsoft Teams Bot"},
        "icons": {"color": "color.png", "outline": "outline.png"},
        "accentColor": "#FFFFFF",
        "bots": [
            {
                "botId": "${{BOT_ID}}",
                "scopes": ["personal", "team", "groupchat"],
                "supportsFiles": False,
                "isNotificationOnly": False,
            }
        ],
        "permissions": ["identity", "messageTeamMembers"],
        "validDomains": [],
    }

    (app_pkg / "manifest.template.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (app_pkg / "README.md").write_text(
        "# App Package\n\n"
        "Fill in `manifest.template.json` with your Bot ID and App ID.\n"
        "Create `color.png` (192×192) and `outline.png` (32×32) icons.\n"
        "Zip this folder and upload to Teams Developer Portal.\n"
    )


def _add_teams_env(target: Path) -> None:
    env_file = target / ".env.example"
    if env_file.exists():
        existing = env_file.read_text()
        if "MicrosoftAppId" not in existing:
            env_file.write_text(
                existing.rstrip() + "\n\n"
                "# Microsoft Teams Bot credentials\n"
                "MicrosoftAppId=\n"
                "MicrosoftAppPassword=\n"
                "MicrosoftAppTenantId=\n"
            )


def _write_dockerfile(cfg: ProjectConfig, target: Path) -> None:
    content = f"""# syntax=docker/dockerfile:1

FROM python:{cfg.python_version}-slim AS builder
ENV UV_PYTHON_DOWNLOADS=0 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install "uv==0.5.29"
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

FROM python:{cfg.python_version}-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd --system app && useradd --system --gid app --create-home app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /code
COPY --from=builder /opt/venv /opt/venv
COPY main.py ./
COPY src/ ./src/
COPY config/ ./config/
USER app
EXPOSE 3978
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
    CMD curl -fsS http://localhost:3978/health || exit 1
CMD ["python", "main.py"]
"""
    (target / "Dockerfile").write_text(content)


def _write_tests(cfg: ProjectConfig, target: Path) -> None:
    tests = target / "tests"
    (tests / "test_bot.py").write_text(f"""import pytest
from aiohttp.test_utils import TestClient, TestServer
from src.{cfg.pkg_name}.app import create_app


@pytest.fixture
async def client(aiohttp_client):
    app = create_app()
    return await aiohttp_client(app)


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
""")
