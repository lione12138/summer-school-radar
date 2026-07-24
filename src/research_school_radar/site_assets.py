from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .atomic_io import write_text_atomic


WEB_ROOT = Path(__file__).with_name("web")
TEMPLATE_ROOT = WEB_ROOT / "templates"
STATIC_ROOT = WEB_ROOT / "static"

_TEMPLATES = Environment(
    loader=FileSystemLoader(TEMPLATE_ROOT),
    autoescape=select_autoescape(("html", "xml")),
    keep_trailing_newline=True,
)


def render_template(template_name: str, **context: Any) -> str:
    """Render a package-owned, autoescaped Jinja template."""
    return _TEMPLATES.get_template(template_name).render(**context)


def read_static_asset(relative_path: str) -> str:
    return (STATIC_ROOT / relative_path).read_text(encoding="utf-8")


def write_static_assets(output_dir: Path) -> None:
    """Copy versioned browser assets into a generated static-site directory."""
    for source in STATIC_ROOT.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(STATIC_ROOT)
        write_text_atomic(output_dir / "assets" / relative, source.read_text(encoding="utf-8"))
