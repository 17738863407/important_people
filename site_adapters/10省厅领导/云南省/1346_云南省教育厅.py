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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.yn.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_yunnan_education_leader_cards_v2",
        "leader_region_selector": ".leader-list .hor-leader-item",
        "name_selector": ".hor-leader-item__name .name",
        "duty_selector": ".hor-leader-item_bottom_text",
        "detail_link_selector": ".hor-leader-item__name .name[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": None,
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
            "candidate_links": [],
        },
        "risk_flag": "fixed_precise_leader_cards_with_detail_links",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".leader-list .hor-leader-item",
                "name_selector": ".hor-leader-item__name .name",
                "duty_selector": ".hor-leader-item_bottom_text",
                "detail_link_selector": ".hor-leader-item__name .name[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "领导列表页链接文本已直接包含姓名和职务"},
            "migration": {"source": "manual_missing_adapter", "verified_status": "pending", "behavior_changed": True},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for card in soup.select(".leader-list .hor-leader-item"):
        name_node = card.select_one(".hor-leader-item__name .name")
        duty_node = card.select_one(".hor-leader-item_bottom_text")
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = normalize_space(duty_node.get_text(" ", strip=True))
        if not is_name(name) or not duty or len(duty) > 120:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_href = name_node.get("href", "").strip()
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, detail_href) if detail_href else "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.leader-list .hor-leader-item；fields=name+duty",
            }
        )

    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1346"
    main(rule_id_value)
