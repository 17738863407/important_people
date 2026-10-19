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


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def clean_name(text: str) -> str:
    return compact_text(text)


def clean_duty(text: str) -> str:
    return normalize_space(text).strip(" ：:，,。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "lr.hainan.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_title_parentheses_direct",
        "collector": "static_http",
        "parser": "page_hainan_resource_leadercon_v1",
        "leader_region_selector": ".xxgk-left .leadercon",
        "name_selector": ".leadercon a[title] title before parentheses",
        "duty_selector": ".leadercon a[title] title inside parentheses",
        "detail_link_selector": ".leadercon a[title][href]",
        "content_scope": {
            "start_anchor": "厅领导信息",
            "end_anchor": "机构概况",
            "include_selectors": [".xxgk-left .leadercon"],
            "exclude_selectors": [".xxgk-right", ".right", "script", "style"],
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
        "risk_flag": "fixed_leadercon_title_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".xxgk-left .leadercon",
                "name_selector": ".leadercon a[title] title before parentheses",
                "duty_selector": ".leadercon a[title] title inside parentheses",
                "detail_link_selector": ".leadercon a[title][href]",
                "content_scope": {
                    "start_anchor": "厅领导信息",
                    "end_anchor": "机构概况",
                    "include_selectors": [".xxgk-left .leadercon"],
                    "exclude_selectors": [".xxgk-right", ".right", "script", "style"],
                },
            },
            "api": {"enabled": False, "reason": "领导信息页正文 leadercon 标题直接包含姓名和职务"},
            "migration": {
                "source": "manual_fix_empty_field_selectors",
                "behavior_changed": True,
            },
        },
    }


def split_title(text: str) -> tuple[str, str]:
    normalized = normalize_space(text)
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[（(](?P<duty>.+?)[）)]$", normalized)
    if not match:
        return "", ""
    name = clean_name(match.group("name"))
    duty = clean_duty(match.group("duty").replace("〈兼〉", "兼"))
    if not is_name(name) or not re.search(r"(书记|厅长|局长|组长)", duty):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    region = soup.select_one(".xxgk-left .leadercon")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[title][href]"):
        title = link.get("title") or link.get_text(" ", strip=True)
        name, duty = split_title(title)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(page_url, link.get("href", "")),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.xxgk-left .leadercon；fields=a[title][href] name+duty；detail_chain=0",
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
    rule_id_value = "1433"
    main(rule_id_value)
