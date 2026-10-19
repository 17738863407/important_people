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
    "rule_id": "0951",
    "page_type": "人物列表完整页",
    "structure_group": "hebsky_profile_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebsky_profile_cards_v1",
    "leader_region_selector": ".min_wygk",
    "name_selector": ".min_gk_sub h2",
    "duty_selector": ".min_gk_sub p",
    "detail_link_selector": ".min_gk_sub > a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".min_wygk"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "person_name_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".min_gk_sub > a[href]",
        "detail_name_selector": "h2",
        "detail_duty_selector": "p",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "人物卡片简介句同时含姓名和多项现职；完整p原文作为依据说明",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".min_wygk",
            "name_selector": ".min_gk_sub h2",
            "duty_selector": ".min_gk_sub p",
            "detail_link_selector": ".min_gk_sub > a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".min_wygk"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML人物卡片直接含姓名、简介原文和独立详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片DOM顺序提取姓名、完整现职句和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".min_wygk")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in scope.select(".min_gk_sub") if scope else []:
        name_node = card.select_one("h2")
        evidence_node = card.select_one("p")
        link_node = card.select_one(":scope > a[href]")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_text(evidence_node.get_text(" ", strip=True)) if evidence_node else ""
        prefix = f"{name}，"
        duty = (evidence[len(prefix) :] if evidence.startswith(prefix) else evidence).removesuffix("。")
        href = link_node.get("href", "").strip() if link_node else ""
        detail_url = urljoin(final_url, href) if href else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_hebsky_profile_cards_v1",
                "selector_summary": ".min_wygk .min_gk_sub；h2姓名、p完整现职句、卡片a详情链接",
            }
        )
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
