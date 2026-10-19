from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


PAGE_RULE: dict[str, Any] = {
    "rule_id": "1501",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#zoom > .TRS_Editor",
    "parser_id": "custom_mct_mixed_prefix_and_paragraph_leaders_v1",
    "structure_group": "混合前缀块与段落_主要职责边界",
    "confidence": "high",
    "risk_notes": "按DOM顺序合并无p的独立前缀块与主要职责前段落；排除职责、组织机构、联系方式表格及页脚二维码iframe。",
}


def _clean(value: str) -> str:
    normalized = value.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"[\s\u200b-\u200d\u2060\ufeff]+", " ", normalized).strip()


def _parse_leader_line(text: str) -> dict[str, str]:
    compact = re.sub(r"\s+", "", _clean(text))
    match = re.fullmatch(
        r"(?P<duty>[^：:]+)[：:](?P<name>[\u3400-\u9fff·]{2,6})",
        compact,
    )
    if match is None:
        raise RuntimeError(f"领导区存在无法解析的文本块：{text}")
    return {
        "name": match.group("name"),
        "duty": match.group("duty"),
        "detail_url": "",
    }


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, Any],
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    scopes = soup.select(page_rule["leader_region_selector"])
    if len(scopes) != 1:
        raise RuntimeError(f"正文编辑器数量异常：{len(scopes)}")

    editor = scopes[0]
    rows: list[dict[str, str]] = []
    for child in editor.find_all(recursive=False):
        if not isinstance(child, Tag):
            continue
        if child.name != "div" and child.find("p") is None:
            text = _clean(child.get_text(" ", strip=True))
            if text:
                rows.append(_parse_leader_line(text))
        if child.name == "div":
            for nested in child.find_all(recursive=False):
                if isinstance(nested, Tag) and nested.find("p") is None:
                    text = _clean(nested.get_text(" ", strip=True))
                    if text:
                        rows.append(_parse_leader_line(text))

    found_end = False
    for paragraph in editor.select("p"):
        text = _clean(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if compact.rstrip("：:") == "主要职责":
            found_end = True
            break
        if compact:
            rows.append(_parse_leader_line(text))

    if not found_end:
        raise RuntimeError("未找到主要职责结束边界")
    if not rows:
        raise RuntimeError("主要职责前未解析到人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
