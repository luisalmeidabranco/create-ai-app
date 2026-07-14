from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    (target / "logs").mkdir(exist_ok=True)
    (target / "logs" / ".gitkeep").write_text("")

    _write_cli(cfg, pkg)
    _write_batch(cfg, pkg)
    _write_processor(cfg, pkg)
    _write_tests(cfg, target)


def _write_cli(cfg: ProjectConfig, pkg: Path) -> None:
    content = f"""from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

import typer

from src.{cfg.pkg_name}.batch import run_batch
from src.{cfg.pkg_name}.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer(name="{cfg.name}", help="{cfg.name} batch processor")


@app.command()
def run(
    input_file: Path = typer.Argument(..., help="Input file to process"),
    output_dir: Path = typer.Option(
        Path("output"),
        "--output", "-o",
        help="Output directory",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing"),
) -> None:
    \"\"\"Run the batch processor.\"\"\"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"results_{{timestamp}}.jsonl"

    logger.info("Starting batch run: input=%s output=%s", input_file, output_file)
    run_batch(input_file, output_file, dry_run=dry_run)
    logger.info("Batch run complete: %s", output_file)
    typer.echo(f"Done. Results: {{output_file}}")


if __name__ == "__main__":
    app()
"""
    (pkg / "cli.py").write_text(content)


def _write_batch(cfg: ProjectConfig, pkg: Path) -> None:
    content = f"""from __future__ import annotations

import json
import logging
from pathlib import Path

from src.{cfg.pkg_name}.processor import process_item

logger = logging.getLogger(__name__)


def run_batch(input_file: Path, output_file: Path, dry_run: bool = False) -> None:
    items = _load_input(input_file)
    logger.info("Loaded %d items", len(items))

    results = []
    for i, item in enumerate(items):
        logger.debug("Processing item %d/%d", i + 1, len(items))
        if dry_run:
            results.append({{"item": item, "result": "dry_run"}})
        else:
            result = process_item(item)
            results.append({{"item": item, "result": result}})

    if not dry_run:
        with open(output_file, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\\n")


def _load_input(path: Path) -> list:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]
    elif suffix == ".json":
        with open(path) as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    else:
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]
"""
    (pkg / "batch.py").write_text(content)


def _write_processor(cfg: ProjectConfig, pkg: Path) -> None:
    content = f"""from __future__ import annotations

import logging
from openai import AzureOpenAI

from src.{cfg.pkg_name}.config import get_settings, get_config

logger = logging.getLogger(__name__)


def process_item(item: str | dict) -> str:
    settings = get_settings()
    cfg = get_config()

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    text = item if isinstance(item, str) else str(item)
    response = client.chat.completions.create(
        model=cfg["llm"]["model"],
        temperature=cfg["llm"].get("temperature", 0.0),
        max_tokens=cfg["llm"].get("max_tokens", 1024),
        messages=[
            {{"role": "system", "content": "Process the following item and return a structured result."}},
            {{"role": "user", "content": text}},
        ],
    )
    return response.choices[0].message.content or ""
"""
    (pkg / "processor.py").write_text(content)


def _write_tests(cfg: ProjectConfig, target: Path) -> None:
    tests = target / "tests"
    (tests / "test_batch.py").write_text(f"""import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_process_item(mock_llm_client, tmp_path):
    with patch("src.{cfg.pkg_name}.processor.get_settings") as ms, \\
         patch("src.{cfg.pkg_name}.processor.get_config") as mc, \\
         patch("src.{cfg.pkg_name}.processor.AzureOpenAI", return_value=mock_llm_client):
        ms.return_value = MagicMock(
            azure_openai_api_key="k",
            azure_openai_endpoint="https://e.openai.azure.com/",
            azure_openai_api_version="2024-12-01-preview",
        )
        mc.return_value = {{"llm": {{"model": "gpt-4o", "temperature": 0.0, "max_tokens": 100}}}}

        from src.{cfg.pkg_name}.processor import process_item
        result = process_item("test item")
        assert result == "mocked response"
""")
