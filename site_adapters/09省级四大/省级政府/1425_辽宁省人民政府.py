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
    return compact_text(text).strip("：:，,。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "page_type": "多人物详情合并页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_nav_links_direct",
        "collector": "static_http",
        "parser": "page_liaoning_government_leader_nav_v1",
        "leader_region_selector": "#leader_one_r .l-box-right ul.clearfix",
        "name_selector": "#leader_one_r .l-box-right ul.clearfix li a leading name",
        "duty_selector": "#leader_one_r .l-box-right ul.clearfix li a trailing duty",
        "detail_link_selector": "#leader_one_r .l-box-right ul.clearfix li a[href]",
        "content_scope": {
            "start_anchor": "政府领导",
            "end_anchor": "活动报道",
            "include_selectors": ["#leader_one_r .l-box-right ul.clearfix"],
            "exclude_selectors": [".gov_navu_two", ".leader_hd", ".leader_sp", ".footer"],
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
        "risk_flag": "online_leader_nav_links_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#leader_one_r .l-box-right ul.clearfix",
                "name_selector": "#leader_one_r .l-box-right ul.clearfix li a leading name",
                "duty_selector": "#leader_one_r .l-box-right ul.clearfix li a trailing duty",
                "detail_link_selector": "#leader_one_r .l-box-right ul.clearfix li a[href]",
                "content_scope": {
                    "start_anchor": "政府领导",
                    "end_anchor": "活动报道",
                    "include_selectors": ["#leader_one_r .l-box-right ul.clearfix"],
                    "exclude_selectors": [".gov_navu_two", ".leader_hd", ".leader_sp", ".footer"],
                },
            },
            "api": {"enabled": False, "reason": "政府领导导航列表直接列出姓名和职务"},
            "migration": {
                "source": "manual_rewrite_broad_detail_chain",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


PAGE_RULE = build_page_rule("1425")


def split_name_duty(text: str) -> tuple[str, str]:
    normalized = normalize_space(text)
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·\s\u3000]{2,8})\s+(?P<duty>省\s*长|副省长|秘书长)$", normalized)
    if not match:
        return "", ""
    name = clean_name(match.group("name"))
    duty = clean_duty(match.group("duty"))
    if not is_name(name) or not duty:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#leader_one_r .l-box-right ul.clearfix")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("li a[href]"):
        name, duty = split_name_duty(link.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#leader_one_r .l-box-right ul.clearfix；fields=leader links text；detail_chain=0",
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
