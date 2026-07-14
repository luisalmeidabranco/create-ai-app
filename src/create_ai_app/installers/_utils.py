from __future__ import annotations

import shutil
from pathlib import Path


def copy_template(template_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, dest_path)


def render_template(template_path: Path, dest_path: Path, replacements: dict[str, str]) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    content = template_path.read_text()
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    dest_path.write_text(content)


def templates_dir() -> Path:
    return Path(__file__).parent.parent / "templates"
