from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4234", "page_type": "领导简介卡片页", "load_mode": "静态 HTML 直出",
    "extract_mode": "card_list", "parser": "page_inline_hn_cma_leaders_v1",
    "leader_region_selector": ".lelayout", "name_selector": ".Lefive a.Lename",
    "duty_selector": ".Lefive p.Leposi", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "confidence": "high", "filter_policy": "strong_card_structure",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """由顶部可见领导卡片的同卡职务与姓名节点提取当前班子。"""
    from bs4 import BeautifulSoup

    rows: list[dict] = []
    for card in BeautifulSoup(html, "html.parser").select(".lelayout > .Lefive"):
        name_node = card.select_one("a.Lename")
        duty_node = card.select_one("p.Leposi")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
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
