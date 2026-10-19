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


def clean_text(value: str) -> str:
    """清理HTML字段中的排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按省局领导列表卡片提取姓名与独立职务字段，排除分工。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".name > ul > li"):
        name_node = card.select_one(".ldzuo h4 strong")
        duty_node = card.select_one(".jjyou > p:not(.jjnr)")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_market_cards_v2",
                "selector_summary": "leader=.name>ul>li；name=.ldzuo h4 strong；duty=.jjyou>p:not(.jjnr)；detail=none",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2269",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_market_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_market_cards_v2",
    "leader_region_selector": ".name > ul > li",
    "name_selector": ".ldzuo h4 strong",
    "duty_selector": ".jjyou > p:not(.jjnr)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "省局领导",
        "end_anchor": "法定职责",
        "include_selectors": [".name"],
        "exclude_selectors": [".jjnr"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".name > ul > li",
            "name_selector": ".ldzuo h4 strong",
            "duty_selector": ".jjyou > p:not(.jjnr)",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "省局领导",
                "end_anchor": "法定职责",
                "include_selectors": [".name"],
                "exclude_selectors": [".jjnr"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML省局领导卡片已提供独立姓名和职务字段"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
