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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"(?<=[、，,])\s+(?=[\u4e00-\u9fff])", "", duty)
    return duty.strip(" ：:，,。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "www.ln.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "leader_info_ul_direct",
        "collector": "static_http",
        "parser": "page_liaoning_government_office_leader_ul_v1",
        "leader_region_selector": "#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul",
        "name_selector": "ul.ldxx_ul li b",
        "duty_selector": "ul.ldxx_ul li text excluding b",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "领导信息",
            "end_anchor": "机关职能",
            "include_selectors": ["#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul"],
            "exclude_selectors": [".xxgk_jgzn", ".footer0", ".zf_search"],
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
        "risk_flag": "leader_info_ul_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul",
                "name_selector": "ul.ldxx_ul li b",
                "duty_selector": "ul.ldxx_ul li text excluding b",
                "detail_link_selector": "",
                "content_scope": {
                    "start_anchor": "领导信息",
                    "end_anchor": "机关职能",
                    "include_selectors": ["#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul"],
                    "exclude_selectors": [".xxgk_jgzn", ".footer0", ".zf_search"],
                },
            },
            "api": {"enabled": False, "reason": "领导信息列表直接列出姓名和职务"},
            "migration": {
                "source": "manual_rewrite_invalid_empty_selectors",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select("li"):
        name_node = item.select_one("b")
        if name_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        name_node.extract()
        duty = clean_duty(item.get_text(" ", strip=True))
        if not is_name(name) or name in seen_names or not duty or len(duty) > 120:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#f3e960c2ddb34757981d776ca504661f ul.ldxx_ul；fields=li b + li remaining text；detail_chain=0",
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
    rule_id_value = "1426"
    main(rule_id_value)
