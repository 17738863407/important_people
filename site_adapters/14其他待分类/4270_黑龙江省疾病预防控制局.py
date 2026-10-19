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
    "rule_id": "4270",
    "page_type": "领导卡片列表",
    "structure_group": "黑龙江疾控局机构领导卡片",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_hlj_cdc_leaders_v1",
    "leader_region_selector": ".inbox.jgld_list",
    "name_selector": ".inbox.jgld_list .jgld_info h3.name",
    "duty_selector": ".inbox.jgld_list .jgld_info .zw",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面详情链接位于HTML注释中，当前可见领导卡片未提供可验证的独立详情页。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """提取当前可见机构领导卡片及其职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".inbox.jgld_list li"):
        name_node = card.select_one(".jgld_info h3.name")
        duty_node = card.select_one(".jgld_info .zw")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        duty = re.sub(r"^职务：", "", duty)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "机构领导卡片姓名和职务字段"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
