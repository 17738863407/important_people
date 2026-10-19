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
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    return normalize_space(text).strip("[]【】 ：:，,。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def is_leader_duty(text: str) -> bool:
    return bool(re.search(r"(书记|厅长|组长|巡视员)", clean_duty(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "lwt.hainan.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_direct",
        "collector": "static_http",
        "parser": "page_hainan_tourism_leader_cards_v1",
        "leader_region_selector": ".gkpd-ld, .gkpd-ldd",
        "name_selector": ".gkpd-ld em, .gkpd-ldd em",
        "duty_selector": ".gkpd-ld span, .gkpd-ldd span",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "一级领导",
            "end_anchor": "二级领导 end",
            "include_selectors": [".gkpd-ld li a", ".gkpd-ldd li a"],
            "exclude_selectors": [".sky-show-phone", ".news-list", ".footer", "script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": "",
            "detail_parser": "",
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
            "candidate_links": [],
        },
        "risk_flag": "desktop_leader_cards_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist_allow_discipline_group",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".gkpd-ld, .gkpd-ldd",
                "name_selector": ".gkpd-ld em, .gkpd-ldd em",
                "duty_selector": ".gkpd-ld span, .gkpd-ldd span",
                "detail_link_selector": "",
                "content_scope": {
                    "start_anchor": "一级领导",
                    "end_anchor": "二级领导 end",
                    "include_selectors": [".gkpd-ld li a", ".gkpd-ldd li a"],
                    "exclude_selectors": [".sky-show-phone", ".news-list", ".footer", "script", "style"],
                },
            },
            "api": {"enabled": False, "reason": "领导信息桌面版卡片已直接包含姓名和职务"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "behavior_changed": True,
            },
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for link in soup.select(".gkpd-ld li a, .gkpd-ldd li a"):
        name_node = link.select_one("em")
        duty_node = link.select_one("span")
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_duty(duty_node.get_text(" ", strip=True))
        if not is_name(name) or not is_leader_duty(duty) or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(page_url, str(link.get("href") or ""))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.gkpd-ld/.gkpd-ldd；fields=em name + span duty；detail_chain=0",
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
    rule_id_value = "1461"
    main(rule_id_value)
