from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4118",
    "page_type": "leader_profile_list",
    "structure_group": "S4118",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.news-txt",
    "risk_notes": "人物块的 h2、h3 分别为职务和中英文姓名，页面未提供个人详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """提取人物块标题中的现职和中文姓名，保留空详情页链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        duty_node = card.select_one(":scope > h2")
        name_node = card.select_one(":scope > h3")
        if duty_node is None or name_node is None:
            continue
        duty = duty_node.get_text(" ", strip=True)
        compact_name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        match = re.match(r"([\u4e00-\u9fff]{2,4})", compact_name)
        if match is None:
            continue
        name = match.group(1)
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
