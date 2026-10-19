from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3956",
    "domain": "www.xcszx.gov.cn",
    "page_type": "人物卡片列表",
    "structure_group": "xuancheng_cppcc_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_xuancheng_cppcc_cards_v1",
    "leader_region_selector": ".purikura",
    "name_selector": ".leader-name",
    "duty_selector": ".leader-text",
    "content_scope": {"include_selectors": [".purikura"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物卡片链接均为javascript:void(0)，不可误填为详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".purikura",
            "record_selector": ".leader, .leader-other li",
            "name_selector": ".leader-name",
            "duty_selector": ".leader-text",
        },
        "api": {"enabled": False, "reason": "静态卡片已直接包含姓名和完整现职"},
    },
}


def normalize_text(value: str) -> str:
    """压缩卡片字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按首卡和其余卡片的DOM顺序提取姓名、完整现职。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".purikura")
    if region is None:
        raise RuntimeError("未找到政协领导卡片区域 .purikura")
    rows: list[dict[str, str]] = []
    for card in region.select(":scope > .leader, :scope > .leader-other li"):
        name_node = card.select_one(".leader-name")
        duty_node = card.select_one(".leader-text")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".purikura首卡及leader-other人物卡片",
            }
        )
    if not rows:
        raise RuntimeError("政协领导卡片区域未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
