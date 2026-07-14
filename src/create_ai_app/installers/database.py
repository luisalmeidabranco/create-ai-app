from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    stores = pkg / "stores"
    stores.mkdir(exist_ok=True)
    (stores / "__init__.py").write_text("")

    db = cfg.database
    if db == "CosmosDB":
        _write_cosmos(cfg, stores)
    elif db == "PostgreSQL":
        _write_postgres(cfg, stores)
    elif db == "SQLite":
        _write_sqlite(cfg, stores)
    elif db == "Redis":
        _write_redis(cfg, stores)


def _write_cosmos(cfg: ProjectConfig, stores: Path) -> None:
    content = f"""from __future__ import annotations

import logging
import os
from typing import Any

from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)

_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
_KEY = os.getenv("COSMOS_KEY", "")
_DB_NAME = os.getenv("COSMOS_DATABASE", "{cfg.name.replace('-', '_')}_db")
_CONTAINER = os.getenv("COSMOS_CONTAINER", "items")


def get_client() -> CosmosClient:
    return CosmosClient(_ENDPOINT, _KEY)


def get_container():
    client = get_client()
    db = client.create_database_if_not_exists(_DB_NAME)
    return db.create_container_if_not_exists(
        id=_CONTAINER,
        partition_key=PartitionKey(path="/id"),
    )


def upsert_item(item: dict[str, Any]) -> dict[str, Any]:
    container = get_container()
    return container.upsert_item(item)


def get_item(item_id: str) -> dict[str, Any] | None:
    try:
        container = get_container()
        return container.read_item(item=item_id, partition_key=item_id)
    except Exception as e:
        logger.warning("Item %s not found: %s", item_id, e)
        return None


def query_items(query: str, params: list | None = None) -> list[dict[str, Any]]:
    container = get_container()
    return list(container.query_items(query=query, parameters=params or [], enable_cross_partition_query=True))
"""
    (stores / "cosmos_store.py").write_text(content)


def _write_postgres(cfg: ProjectConfig, stores: Path) -> None:
    content = f"""from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/{cfg.pkg_name}")

engine = create_async_engine(_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
"""
    (stores / "pg_store.py").write_text(content)


def _write_sqlite(cfg: ProjectConfig, stores: Path) -> None:
    content = f"""from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DB_PATH = os.getenv("SQLITE_PATH", "{cfg.name}.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        \"\"\")
        conn.commit()
"""
    (stores / "sqlite_store.py").write_text(content)


def _write_redis(cfg: ProjectConfig, stores: Path) -> None:
    content = """from __future__ import annotations

import json
import os
from typing import Any

import redis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(_REDIS_URL, decode_responses=True)
    return _client


def set_value(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    client = get_client()
    serialized = json.dumps(value)
    if ttl_seconds:
        client.setex(key, ttl_seconds, serialized)
    else:
        client.set(key, serialized)


def get_value(key: str) -> Any | None:
    client = get_client()
    raw = client.get(key)
    return json.loads(raw) if raw else None


def delete_value(key: str) -> None:
    get_client().delete(key)
"""
    (stores / "redis_store.py").write_text(content)
