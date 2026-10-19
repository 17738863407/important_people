from __future__ import annotations

import sys
from pathlib import Path


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按经营管理层人物卡片提取姓名及简介首句中的现职依据。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("div.crc-lb-manage-wenben"):
        name_node = card.select_one("div.crc-lb-manage-wenben-title")
        duty_node = card.select_one("div.crc-lb-manage-wenben-desc")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"(?:先生|女士)$", "", name_node.get_text(" ", strip=True)).strip()
        profile = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        duty_match = re.match(r"^[^。]+。", profile)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or duty_match is None:
            continue
        duty = duty_match.group(0).removeprefix("现任").strip().removesuffix("。")
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_parse_management_card_intro_v1",
                "detail_url": "",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3484",
    "page_type": "经营管理层人物卡片",
    "structure_group": "crc_management_card_intro",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_parse_management_card_intro_v1",
    "leader_region_selector": "div.crc-lb-right-manage",
    "name_selector": "div.crc-lb-manage-wenben-title",
    "duty_selector": "div.crc-lb-manage-wenben-desc",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "简介首句是当前经营管理层职务，后续为其他任职和历史履历",
    "confidence": "high",
}

def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


if __name__ == "__main__":
    main()
