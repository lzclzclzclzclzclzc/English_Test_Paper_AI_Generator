"""Prompt template loader.

Loads markdown prompt files from ai_engine/prompts/, renders with Jinja2,
and returns (system, user) tuple separated by --- line.
"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _to_json(value) -> str:
    """Jinja2 filter: convert value to JSON string."""
    return json.dumps(value, ensure_ascii=False, indent=2)


_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["to_json"] = _to_json


def load(name: str, **vars) -> tuple[str, str]:
    """Load prompts/<name>.md, render with Jinja2, return (system, user).
    
    The prompt file must use --- to separate system and user sections.
    """
    template = _env.get_template(f"{name}.md")
    content = template.render(**vars)
    
    parts = content.split("---")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    else:
        return "", content.strip()
