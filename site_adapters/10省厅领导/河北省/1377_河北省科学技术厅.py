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
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def split_name_and_duty(text: str) -> tuple[str, str]:
    normalized = normalize_space(text)
    match = re.match(
        r"^(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>(?:党组|一级|二级|三级|四级|厅长|副厅长).+)$",
        normalized,
    )
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_duty(match.group("duty"))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.hebei.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_hebei_science_leader_items_v2",
        "leader_region_selector": "#xxgk-right .ldItem",
        "name_selector": "#xxgk-right .ldItem text leading name",
        "duty_selector": "#xxgk-right .ldItem text after name",
        "detail_link_selector": "",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#xxgk-right"], "exclude_selectors": []},
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
        "risk_flag": "leader_item_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#xxgk-right .ldItem",
                "name_selector": ".ldItem text leading name",
                "duty_selector": ".ldItem text after name",
                "detail_link_selector": "",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#xxgk-right"], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "厅领导信息正文表格单元格直接列出姓名和职务"},
            "migration": {
                "source": "manual_fix_existing_adapter",
                "behavior_changed": True,
            },
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#xxgk-right") or soup.select_one(".xxgk-right.column")
    if not region:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select(".ldItem"):
        text = normalize_space(item.get_text(" ", strip=True))
        name, duty = split_name_and_duty(text)
        if name in seen_names or not is_name(name) or not duty or len(duty) > 100:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#xxgk-right .ldItem；fields=item text 姓名 职务；detail_chain=0",
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
    rule_id_value = "1377"
    main(rule_id_value)
