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
    duty = normalize_space(text)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def split_name_duty(text: str) -> tuple[str, str]:
    normalized = normalize_space(text)
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[-－—]\s*(?P<duty>.+)$", normalized)
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_duty(match.group("duty"))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.yn.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "leader_members_text_direct",
        "collector": "static_http",
        "parser": "page_yunnan_science_leader_members_text_v1",
        "leader_region_selector": ".scroll_wrap whose header is 领导成员",
        "name_selector": "leader members a text before hyphen",
        "duty_selector": "leader members a text after hyphen",
        "detail_link_selector": "leader members a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [".scroll_wrap"],
            "exclude_selectors": [],
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
        "risk_flag": "fixed_leader_members_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".scroll_wrap whose header is 领导成员",
                "name_selector": "leader members a text before hyphen",
                "duty_selector": "leader members a text after hyphen",
                "detail_link_selector": "leader members a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [".scroll_wrap"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导成员栏目列表已直接列出姓名和职务"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def find_leader_region(soup: BeautifulSoup):
    for region in soup.select(".scroll_wrap"):
        title = normalize_space(region.select_one(".zfxxgk_head span").get_text(" ", strip=True)) if region.select_one(".zfxxgk_head span") else ""
        if title == "领导成员":
            return region
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = find_leader_region(soup)
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("li span a[href]"):
        name, duty = split_name_duty(link.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names or not duty or len(duty) > 120:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.scroll_wrap header 领导成员；fields=a text 姓名-职务；detail_chain=0",
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
    rule_id_value = "1392"
    main(rule_id_value)
