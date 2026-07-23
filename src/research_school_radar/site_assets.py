from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

from .atomic_io import write_text_atomic


WEB_ROOT = Path(__file__).with_name("web")
TEMPLATE_ROOT = WEB_ROOT / "templates"
STATIC_ROOT = WEB_ROOT / "static"


def render_template(name: str, **context: Any) -> str:
    """Render a package-owned HTML shell with already escaped HTML fragments."""
    source = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
    values = {key: str(value) for key, value in context.items()}
    return Template(source).substitute(values)


def read_static_asset(relative_path: str) -> str:
    return (STATIC_ROOT / relative_path).read_text(encoding="utf-8")


def write_static_assets(output_dir: Path) -> None:
    """Copy versioned browser assets into a generated static-site directory."""
    for source in STATIC_ROOT.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(STATIC_ROOT)
        write_text_atomic(output_dir / "assets" / relative, source.read_text(encoding="utf-8"))
