from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    _write_main(cfg, target)
    _write_gunicorn_conf(target)
    _write_router(cfg, target)
    _write_schemas(cfg, target)
    _write_services(cfg, target)
    _write_tests(cfg, target)


def _write_main(cfg: ProjectConfig, target: Path) -> None:
    framework = cfg.api_framework
    if framework == "FastAPI":
        content = f"""import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.{cfg.pkg_name}.config import get_config, get_settings
from src.{cfg.pkg_name}.logging_config import configure_logging
from src.{cfg.pkg_name}.router import router

configure_logging()
logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:3000", "http://localhost:3001"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_config()
    get_settings()
    logger.info("{cfg.name} API started.")
    yield


app = FastAPI(title="{cfg.name}", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {{"status": "ok"}}
"""
    elif framework == "Flask":
        content = f"""import logging
from flask import Flask
from src.{cfg.pkg_name}.config import get_settings
from src.{cfg.pkg_name}.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/health")
def health():
    return {{"status": "ok"}}
"""
    elif framework == "Chainlit":
        content = f"""import chainlit as cl
import logging
from src.{cfg.pkg_name}.config import get_settings
from src.{cfg.pkg_name}.logging_config import configure_logging
from src.{cfg.pkg_name}.services import run_agent

configure_logging()
logger = logging.getLogger(__name__)


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="Hello! How can I help you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    response = await run_agent(message.content)
    await cl.Message(content=response).send()
"""
    elif framework == "Streamlit":
        content = f"""import streamlit as st
import logging
from src.{cfg.pkg_name}.config import get_settings
from src.{cfg.pkg_name}.logging_config import configure_logging
from src.{cfg.pkg_name}.services import run_agent

configure_logging()
logger = logging.getLogger(__name__)

st.title("{cfg.name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Ask something..."):
    st.session_state.messages.append({{"role": "user", "content": prompt}})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        response = run_agent(prompt)
        st.write(response)
    st.session_state.messages.append({{"role": "assistant", "content": response}})
"""
    else:
        return

    (target / "main.py").write_text(content)


def _write_gunicorn_conf(target: Path) -> None:
    content = """import os

accesslog = "-"
errorlog = "-"
bind = "0.0.0.0:3100"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "180"))
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "50"))
"""
    (target / "gunicorn.conf.py").write_text(content)


def _write_router(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name

    auth_imports = ""
    auth_dep = ""
    if cfg.auth == "API key header":
        auth_imports = f"""from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from src.{cfg.pkg_name}.config import get_settings

_api_key_header = APIKeyHeader(name=get_settings().app_api_key_header, auto_error=True)


def _verify_api_key(key: str = Security(_api_key_header)) -> str:
    if key != get_settings().app_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return key

"""
        auth_dep = ", dependencies=[Depends(_verify_api_key)]"
    elif cfg.auth == "Azure Entra ID":
        auth_imports = f"""from fastapi import Depends
from src.{cfg.pkg_name}.auth import verify_token

"""
        auth_dep = ", dependencies=[Depends(verify_token)]"

    content = f"""import logging
from fastapi import APIRouter
{auth_imports}
from src.{cfg.pkg_name}.schemas import RequestPayload, ResponsePayload
from src.{cfg.pkg_name}.services import process_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Public health check — no auth required
@router.get("/health")
async def health():
    return {{"status": "ok"}}


# Protected routes
_protected = APIRouter({auth_dep.lstrip(", ")})


@_protected.post("/process", response_model=ResponsePayload)
async def process(payload: RequestPayload) -> ResponsePayload:
    logger.debug("Processing request: %s", payload.input[:100])
    result = await process_request(payload)
    return result


router.include_router(_protected)
"""
    (pkg / "router.py").write_text(content)


def _write_schemas(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    content = """from pydantic import BaseModel


class RequestPayload(BaseModel):
    input: str
    context: dict = {}


class ResponsePayload(BaseModel):
    output: str
    metadata: dict = {}
"""
    (pkg / "schemas.py").write_text(content)


def _write_services(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name

    if cfg.uses_azure_openai or cfg.llm_backend == "Multiple":
        top_import = "from openai import AzureOpenAI"
        client_init = """    settings = get_settings()
    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )"""
    elif cfg.llm_backend == "OpenAI.com":
        top_import = "from openai import OpenAI"
        client_init = """    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)"""
    elif cfg.llm_backend == "Anthropic":
        top_import = "import anthropic"
        client_init = """    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)"""
    else:
        top_import = "from openai import AzureOpenAI"
        client_init = """    settings = get_settings()
    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )"""

    content = f"""from __future__ import annotations

import logging

{top_import}

from src.{cfg.pkg_name}.config import get_config, get_settings
from src.{cfg.pkg_name}.schemas import RequestPayload, ResponsePayload

logger = logging.getLogger(__name__)


async def process_request(payload: RequestPayload) -> ResponsePayload:
    cfg = get_config()
{client_init}

    system_prompt_path = "src/{cfg.pkg_name}/resources/prompts/system_prompt.md"
    try:
        with open(system_prompt_path) as f:
            system_prompt = f.read()
    except FileNotFoundError:
        system_prompt = "You are a helpful AI assistant."

    response = client.chat.completions.create(
        model=cfg["llm"]["model"],
        temperature=cfg["llm"].get("temperature", 0.0),
        max_tokens=cfg["llm"].get("max_tokens", 4096),
        messages=[
            {{"role": "system", "content": system_prompt}},
            {{"role": "user", "content": payload.input}},
        ],
    )

    output = response.choices[0].message.content or ""
    logger.debug("LLM response length: %d chars", len(output))
    return ResponsePayload(output=output)
"""
    (pkg / "services.py").write_text(content)


def _write_tests(cfg: ProjectConfig, target: Path) -> None:
    tests = target / "tests"

    auth_header_fixture = ""
    auth_headers_arg = ""
    if cfg.auth == "API key header":
        auth_header_fixture = """

@pytest.fixture(autouse=True)
def mock_settings_api_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("APP_API_KEY_HEADER", "X-API-Key")
"""
        auth_headers_arg = ', headers={"X-API-Key": "test-key"}'

    (tests / "test_router.py").write_text(f"""import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app

client = TestClient(app)
{auth_header_fixture}

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
""")

    llm_cls = "AzureOpenAI" if cfg.uses_azure_openai or cfg.llm_backend == "Multiple" else (
        "OpenAI" if cfg.llm_backend == "OpenAI.com" else "Anthropic"
    )
    llm_settings = ""
    if cfg.uses_azure_openai or cfg.llm_backend == "Multiple":
        llm_settings = """MagicMock(
            azure_openai_api_key="test",
            azure_openai_endpoint="https://test.openai.azure.com/",
            azure_openai_api_version="2024-12-01-preview",
        )"""
    elif cfg.llm_backend == "OpenAI.com":
        llm_settings = 'MagicMock(openai_api_key="test")'
    else:
        llm_settings = 'MagicMock(anthropic_api_key="test")'

    (tests / "test_services.py").write_text(f"""import pytest
from unittest.mock import MagicMock, patch

from src.{cfg.pkg_name}.schemas import RequestPayload
from src.{cfg.pkg_name}.services import process_request


async def test_process_request(mock_llm_client):
    payload = RequestPayload(input="test input")

    with patch("src.{cfg.pkg_name}.services.get_settings") as mock_settings, \\
         patch("src.{cfg.pkg_name}.services.get_config") as mock_config, \\
         patch("src.{cfg.pkg_name}.services.{llm_cls}", return_value=mock_llm_client):

        mock_settings.return_value = {llm_settings}
        mock_config.return_value = {{"llm": {{"model": "gpt-4o", "temperature": 0.0, "max_tokens": 100}}}}

        result = await process_request(payload)

    assert result.output == "mocked response"
""")
