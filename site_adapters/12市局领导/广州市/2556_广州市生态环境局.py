from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2556",
    "page_type": "人物表格页",
    "structure_group": "表格行姓名职务与简介分工复合结构",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content table",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每行同时含姓名职务、分工和简介，职务必须截断于分工标签之前",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    """移除表格排版空白，保留原始标点和字段内容。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格行顺序解析分工标签之前的姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for table_row in soup.select(".article-content table tr"):
        row_text = table_row.get_text(" ", strip=True)
        header = re.split(r"分工\s*[：:]", row_text, maxsplit=1)[0]
        intro_match = re.search(
            r"简介\s*[：:]\s*(?P<name>[\u4e00-\u9fff·\s]{2,8})[，,]",
            row_text,
        )
        if intro_match is None:
            continue
        name = compact_text(intro_match.group("name"))
        compact_header = compact_text(header)
        if not compact_header.startswith(name):
            continue
        duty = compact_header[len(name) :].strip("，,：:")
        if not duty or name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article-content表格行内分工标签之前的姓名与职务",
            }
        )
        seen.add(name)

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
