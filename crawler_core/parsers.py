from __future__ import annotations

from pathlib import Path
from typing import Any

from crawler_core.models import PersonRecord
from crawler_core.parser_registry import parse_with_registered_parser


def parse_generic_confirmed_page(
    rule: dict[str, Any],
    html: str,
    snapshot_path: Path | None = None,
    final_url: str = "",
) -> list[PersonRecord]:
    """兼容旧入口，实际调用版本化解析器注册表。"""
    return parse_with_registered_parser(rule, html, final_url, snapshot_path)
