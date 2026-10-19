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
    """清理字段排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介卡片顺序提取独立姓名和职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("div.ldjs .ls-leader-item"):
        name_node = card.select_one(".ls-leader-name")
        duty_node = card.select_one(".ls-leader-positions")
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
                "parser": "page_inline_qinghai_agency_affairs_cards_v2",
                "selector_summary": "leader=div.ldjs .ls-leader-item；name=.ls-leader-name；duty=.ls-leader-positions；detail=none",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2349",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_agency_affairs_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_agency_affairs_cards_v2",
    "leader_region_selector": "div.ldjs .ls-leader-item",
    "name_selector": ".ls-leader-name",
    "duty_selector": ".ls-leader-positions",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.ldjs"],
        "exclude_selectors": [".ls-leader-resume"],
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
            "leader_region_selector": "div.ldjs .ls-leader-item",
            "name_selector": ".ls-leader-name",
            "duty_selector": ".ls-leader-positions",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["div.ldjs"],
                "exclude_selectors": [".ls-leader-resume"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML卡片已提供独立姓名和职务字段"},
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
