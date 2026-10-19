from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3947",
    "domain": "www.nczx.gov.cn",
    "page_type": "职务分组人物卡片",
    "structure_group": "nanchong_cppcc_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_nanchong_cppcc_cards_v1",
    "leader_region_selector": ".leader-list",
    "name_selector": ".info-title",
    "duty_selector": ".leader-down-title",
    "detail_link_selector": ".info-list > a[href]",
    "content_scope": {"include_selectors": [".leader-list"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "职务位于分组标题，需限定当前分组内的人物卡片并继承网页顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leader-list",
            "group_selector": ".leader-down",
            "duty_selector": ".leader-down-title",
            "name_selector": ".info-title",
            "detail_link_selector": ".info-list > a[href]",
        },
        "api": {"enabled": False, "reason": "静态HTML卡片已直接包含职务分组、姓名和详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """压缩字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务分组和卡片DOM顺序提取领导。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader-list")
    if region is None:
        raise RuntimeError("未找到政协领导卡片区域 .leader-list")
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > .leader-down"):
        title = group.select_one(".leader-down-title")
        duty = normalize_text(title.get_text(" ", strip=True) if title else "")
        if duty not in {"主席", "副主席", "秘书长"}:
            continue
        for card in group.select(".leader-down-info .info-list"):
            name_node = card.select_one(".info-title")
            link = card.select_one("a[href]")
            name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))) if link else "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".leader-down职务分组内.info-list人物卡片",
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
