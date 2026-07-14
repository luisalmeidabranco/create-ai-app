from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    # base.py already writes the rotating-file variant; overwrite for other styles.
    if cfg.logging_style in ("basic", "Basic basicConfig"):
        _write_basic(cfg, target)
    elif cfg.logging_style in ("json", "JSON structured"):
        _write_json(cfg, target)
    # "rotating" / "Rotating file module" → already correct from base.py


def _write_basic(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    content = '''from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
'''
    (pkg / "logging_config.py").write_text(content)


def _write_json(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    content = '''from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
        })


def configure_logging() -> None:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
'''
    (pkg / "logging_config.py").write_text(content)
