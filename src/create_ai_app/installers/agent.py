from __future__ import annotations

import json
from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name

    for subpkg in ("agents", "tools", "memory"):
        d = pkg / subpkg
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text("")

    if cfg.uses_maf:
        _write_maf(cfg, pkg)
    elif cfg.agent_framework == "LangGraph":
        _write_langgraph(cfg, pkg)
    elif cfg.agent_framework == "AutoGen":
        _write_autogen(cfg, pkg)
    elif cfg.agent_framework == "LangChain":
        _write_langchain(cfg, pkg)
    else:
        _write_raw_sdk(cfg, pkg)

    _write_tools(pkg, cfg.ai_context)
    _write_memory(pkg)
    _write_tests(cfg, target)

    if cfg.api_framework == "FastAPI" and not cfg.is_rest_api:
        from create_ai_app.installers import api as api_installer
        api_installer.install(cfg, target)
    elif cfg.api_framework == "Chainlit":
        _write_chainlit_main(cfg, target, pkg)
    elif cfg.api_framework == "Streamlit":
        _write_streamlit_main(cfg, target, pkg)


# ── MAF ──────────────────────────────────────────────────────────────────────

def _write_maf(cfg: ProjectConfig, pkg: Path) -> None:
    ai = cfg.ai_context or {}
    agent_names = ai.get("agent_names") or ["Triage", "Specialist"]
    triage_name = agent_names[0]
    specialist_name = agent_names[1] if len(agent_names) > 1 else "Specialist"
    triage_prompt = ai.get("triage_prompt") or (
        f"You are the entry point for {cfg.name}. Understand the user's intent "
        f"and route to the appropriate specialist, or answer directly for simple questions."
    )
    specialist_prompt = ai.get("specialist_prompt") or (
        f"You are a specialist for {cfg.name}. "
        f"You receive tasks routed from the triage agent. Provide clear, structured responses."
    )

    ctx = pkg / "context_providers"
    ctx.mkdir(exist_ok=True)
    (ctx / "__init__.py").write_text(
        "from .search_provider import SearchContextProvider\n"
        "from .history_provider import HistoryContextProvider\n"
    )

    (ctx / "search_provider.py").write_text(f"""from __future__ import annotations
import os
from agent_framework import ContextProvider, Context
from azure.search.documents.aio import SearchClient
from azure.identity import DefaultAzureCredential


class SearchContextProvider(ContextProvider):
    \"\"\"Retrieves relevant documents from Azure AI Search.\"\"\"

    def __init__(self):
        self._client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT", ""),
            index_name=os.getenv("AZURE_SEARCH_INDEX", ""),
            credential=DefaultAzureCredential(),
        )

    async def invoking(self, messages, **kwargs) -> Context:
        query = messages[-1].content if messages else ""
        results = await self._client.search(search_text=query, top=5)
        docs = [r["content"] async for r in results if "content" in r]
        return Context(content="\\n\\n".join(docs))
""")

    (ctx / "history_provider.py").write_text(f"""from __future__ import annotations
from agent_framework import ContextProvider, Context
from src.{pkg.name}.memory.store import InMemoryStore

_store = InMemoryStore()


class HistoryContextProvider(ContextProvider):
    \"\"\"Injects recent conversation turns as context.\"\"\"

    def __init__(self, session_id: str, max_turns: int = 10):
        self._session_id = session_id
        self._max_turns = max_turns

    async def invoking(self, messages, **kwargs) -> Context:
        history = _store.get(self._session_id)[-self._max_turns:]
        formatted = "\\n".join(f"{{m['role']}}: {{m['content']}}" for m in history)
        return Context(content=formatted or "No conversation history yet.")
""")

    prompts = pkg / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "_loader.py").write_text("""from __future__ import annotations
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    return (Path(__file__).parent / f"{name}.md").read_text(encoding="utf-8")
""")
    (prompts / "triage.md").write_text(f"# {triage_name}\n\n{triage_prompt}\n")
    (prompts / "specialist.md").write_text(f"# {specialist_name}\n\n{specialist_prompt}\n")

    storage = pkg / "storage"
    storage.mkdir(exist_ok=True)
    (storage / "__init__.py").write_text("")
    if cfg.database == "CosmosDB":
        (storage / "cosmos_store.py").write_text(f"""from __future__ import annotations
import os
from azure.cosmos.aio import CosmosClient
from azure.identity import DefaultAzureCredential

_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
_DB = os.getenv("COSMOS_DATABASE", "{cfg.name.replace('-', '_')}_db")
_CONTAINER = os.getenv("COSMOS_CONTAINER", "sessions")


def get_client() -> CosmosClient:
    return CosmosClient(_ENDPOINT, credential=DefaultAzureCredential())


async def get_container():
    db = get_client().get_database_client(_DB)
    return db.get_container_client(_CONTAINER)
""")

    (pkg / "agents" / "triage.py").write_text(f"""from __future__ import annotations
import logging
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.{pkg.name}.config import get_settings
from src.{pkg.name}.context_providers import SearchContextProvider, HistoryContextProvider
from src.{pkg.name}.prompts._loader import load_prompt

logger = logging.getLogger(__name__)


def build_triage_agent(session_id: str = "default"):
    settings = get_settings()
    client = AzureOpenAIChatClient(
        credential=DefaultAzureCredential(),
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment,
    )
    return client.as_agent(
        name="{triage_name}",
        instructions=load_prompt("triage"),
        context_providers=[
            SearchContextProvider(),
            HistoryContextProvider(session_id),
        ],
    )
""")

    (pkg / "agents" / "specialist.py").write_text(f"""from __future__ import annotations
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.{pkg.name}.config import get_settings
from src.{pkg.name}.prompts._loader import load_prompt


def build_specialist_agent():
    settings = get_settings()
    client = AzureOpenAIChatClient(
        credential=DefaultAzureCredential(),
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment,
    )
    return client.as_agent(name="{specialist_name}", instructions=load_prompt("specialist"))
""")

    (pkg / "services.py").write_text(f"""from __future__ import annotations
import logging
from agent_framework.orchestrations import HandoffBuilder

from src.{pkg.name}.agents.triage import build_triage_agent
from src.{pkg.name}.agents.specialist import build_specialist_agent

logger = logging.getLogger(__name__)


async def orchestrate(user_message: str, session_id: str = "default") -> str:
    triage = build_triage_agent(session_id)
    specialist = build_specialist_agent()

    builder = HandoffBuilder()
    builder.add_agent(triage, is_entry=True)
    builder.add_agent(specialist)
    # TODO: builder.add_handoff(triage, specialist, condition=...)

    orchestrator = builder.build()
    result = await orchestrator.run(user_message)
    return result.text
""")

    _patch_config_for_maf(pkg)


def _patch_config_for_maf(pkg: Path) -> None:
    config_path = pkg / "config.py"
    content = config_path.read_text()
    if "azure_openai_deployment" not in content:
        content = content.replace(
            '    azure_openai_api_version: str = "2024-12-01-preview"',
            (
                '    azure_openai_api_version: str = "2024-12-01-preview"\n'
                '    azure_openai_deployment: str = "gpt-4o"\n'
                '    azure_search_endpoint: str = ""\n'
                '    azure_search_index: str = ""\n'
                '    cosmos_endpoint: str = ""'
            ),
        )
        config_path.write_text(content)


# ── Raw SDK ───────────────────────────────────────────────────────────────────

def _write_raw_sdk(cfg: ProjectConfig, pkg: Path) -> None:
    (pkg / "agents" / "agent.py").write_text(f"""from __future__ import annotations
import logging
from openai import AzureOpenAI

from src.{pkg.name}.config import get_settings, get_config
from src.{pkg.name}.tools.tools import get_tools, handle_tool_call

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self):
        settings = get_settings()
        cfg = get_config()
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self._model = cfg["llm"]["model"]
        self._tools = get_tools()
        self._messages: list = []

    def run(self, user_input: str) -> str:
        self._messages.append({{"role": "user", "content": user_input}})
        while True:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self._messages,
                tools=self._tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message
            self._messages.append(msg)
            if not msg.tool_calls:
                return msg.content or ""
            for tc in msg.tool_calls:
                result = handle_tool_call(tc.function.name, tc.function.arguments)
                self._messages.append({{
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                }})
""")

    (pkg / "services.py").write_text(f"""from __future__ import annotations
from src.{pkg.name}.agents.agent import Agent

_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


async def orchestrate(user_message: str, session_id: str = "default") -> str:
    return get_agent().run(user_message)
""")


# ── LangGraph ─────────────────────────────────────────────────────────────────

def _write_langgraph(cfg: ProjectConfig, pkg: Path) -> None:
    (pkg / "agents" / "graph.py").write_text(f"""from __future__ import annotations
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI

from src.{pkg.name}.config import get_settings


class AgentState(TypedDict):
    messages: list


def build_graph():
    settings = get_settings()
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o",
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    graph = StateGraph(AgentState)
    # TODO: add nodes, edges, and entry point
    return graph.compile()


_graph = build_graph()
""")
    (pkg / "services.py").write_text(f"""from __future__ import annotations
from src.{pkg.name}.agents.graph import _graph


async def orchestrate(user_message: str, session_id: str = "default") -> str:
    result = await _graph.ainvoke({{"messages": [{{"role": "user", "content": user_message}}]}})
    return result["messages"][-1].content
""")


# ── AutoGen ───────────────────────────────────────────────────────────────────

def _write_autogen(cfg: ProjectConfig, pkg: Path) -> None:
    (pkg / "agents" / "autogen_agents.py").write_text(f"""from __future__ import annotations
import autogen
from src.{pkg.name}.config import get_settings


def build_agents():
    settings = get_settings()
    llm_config = {{
        "model": "gpt-4o",
        "api_key": settings.azure_openai_api_key,
        "base_url": settings.azure_openai_endpoint,
        "api_type": "azure",
        "api_version": settings.azure_openai_api_version,
    }}
    assistant = autogen.AssistantAgent("assistant", llm_config=llm_config)
    user_proxy = autogen.UserProxyAgent("user_proxy", human_input_mode="NEVER",
                                        max_consecutive_auto_reply=5)
    return assistant, user_proxy
""")
    (pkg / "services.py").write_text(f"""from __future__ import annotations
from src.{pkg.name}.agents.autogen_agents import build_agents


async def orchestrate(user_message: str, session_id: str = "default") -> str:
    assistant, user_proxy = build_agents()
    result = user_proxy.initiate_chat(assistant, message=user_message)
    return result.summary or ""
""")


# ── LangChain ─────────────────────────────────────────────────────────────────

def _write_langchain(cfg: ProjectConfig, pkg: Path) -> None:
    (pkg / "agents" / "lc_agent.py").write_text(f"""from __future__ import annotations
from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from src.{pkg.name}.config import get_settings
from src.{pkg.name}.tools.tools import get_langchain_tools


def build_agent() -> AgentExecutor:
    settings = get_settings()
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o",
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    tools = get_langchain_tools()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant."),
        ("placeholder", "{{messages}}"),
        ("placeholder", "{{agent_scratchpad}}"),
    ])
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)
""")
    (pkg / "services.py").write_text(f"""from __future__ import annotations
from src.{pkg.name}.agents.lc_agent import build_agent

_executor = None


async def orchestrate(user_message: str, session_id: str = "default") -> str:
    global _executor
    if _executor is None:
        _executor = build_agent()
    result = await _executor.ainvoke({{"messages": [{{"role": "user", "content": user_message}}]}})
    return result.get("output", "")
""")


# ── shared helpers ────────────────────────────────────────────────────────────

def _write_tools(pkg: Path, ai_ctx: dict | None = None) -> None:
    ai_tools = (ai_ctx or {}).get("tools") or []

    if ai_tools:
        tool_defs = []
        handler_cases = []
        for t in ai_tools:
            params = t.get("parameters") or [{"name": "input", "type": "str"}]
            props = {p["name"]: {"type": "string"} for p in params}
            required = [p["name"] for p in params]
            tool_defs.append(
                f'        {{\n'
                f'            "type": "function",\n'
                f'            "function": {{\n'
                f'                "name": "{t["name"]}",\n'
                f'                "description": "{t["description"]}",\n'
                f'                "parameters": {{\n'
                f'                    "type": "object",\n'
                f'                    "properties": {json.dumps(props)},\n'
                f'                    "required": {json.dumps(required)},\n'
                f'                }},\n'
                f'            }},\n'
                f'        }}'
            )
            first_param = params[0]["name"] if params else "input"
            handler_cases.append(
                f'    if name == "{t["name"]}":\n'
                f'        # TODO: implement {t["name"]}\n'
                f'        return f"{t["name"]} result for: {{args.get(\"{first_param}\")}}"\n'
            )

        tools_list = ",\n".join(tool_defs)
        handler_body = "".join(handler_cases)
        content = f'''from __future__ import annotations
import json


def get_tools() -> list[dict]:
    return [
{tools_list}
    ]


def handle_tool_call(name: str, arguments: str) -> str:
    args = json.loads(arguments)
{handler_body}    return f"Unknown tool: {{name}}"


def get_langchain_tools() -> list:
    return []
'''
    else:
        content = '''from __future__ import annotations
import json


def get_tools() -> list[dict]:
    """Return OpenAI-format tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "example_tool",
                "description": "An example tool — replace with real tools.",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                },
            },
        }
    ]


def handle_tool_call(name: str, arguments: str) -> str:
    args = json.loads(arguments)
    if name == "example_tool":
        return f"Tool result for: {args.get(\'input\')}"
    return f"Unknown tool: {name}"


def get_langchain_tools() -> list:
    return []
'''

    (pkg / "tools" / "tools.py").write_text(content)
    (pkg / "tools" / "__init__.py").write_text(
        "from .tools import get_tools, handle_tool_call, get_langchain_tools\n"
    )


def _write_memory(pkg: Path) -> None:
    (pkg / "memory" / "store.py").write_text('''from __future__ import annotations
from typing import Any


class InMemoryStore:
    """Simple in-process conversation memory."""

    def __init__(self):
        self._store: dict[str, list] = {}

    def get(self, session_id: str) -> list:
        return self._store.get(session_id, [])

    def add(self, session_id: str, message: dict[str, Any]) -> None:
        self._store.setdefault(session_id, []).append(message)

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
''')
    (pkg / "memory" / "__init__.py").write_text("from .store import InMemoryStore\n")


def _write_chainlit_main(cfg: ProjectConfig, target: Path, pkg: Path) -> None:
    (target / "main.py").write_text(f"""import chainlit as cl
import logging
from src.{pkg.name}.services import orchestrate
from src.{pkg.name}.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("session_id", cl.context.session.id)
    await cl.Message(content="Hello! How can I help you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("session_id", "default")
    response = await orchestrate(message.content, session_id=session_id)
    await cl.Message(content=response).send()
""")


def _write_streamlit_main(cfg: ProjectConfig, target: Path, pkg: Path) -> None:
    (target / "main.py").write_text(f"""import streamlit as st
import asyncio
import logging
from src.{pkg.name}.services import orchestrate
from src.{pkg.name}.logging_config import configure_logging

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
        response = asyncio.run(orchestrate(prompt))
        st.write(response)
    st.session_state.messages.append({{"role": "assistant", "content": response}})
""")


def _write_tests(cfg: ProjectConfig, target: Path) -> None:
    tests = target / "tests"
    (tests / "test_agent.py").write_text(f"""import pytest
from unittest.mock import patch, AsyncMock


async def test_orchestrate():
    with patch("src.{cfg.pkg_name}.services.orchestrate", new_callable=AsyncMock) as mock_orch:
        mock_orch.return_value = "test response"
        from src.{cfg.pkg_name}.services import orchestrate
        result = await orchestrate("hello")
        assert isinstance(result, str)
""")
