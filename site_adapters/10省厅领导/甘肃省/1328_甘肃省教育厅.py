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
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.gansu.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "gansu_education_leader_cards_v2",
        "reuse_scope": "single_page",
        "load_mode": "动态DOM渲染",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "browser_dom",
        "parser": "page_gansu_education_leader_cards_v2",
        "leader_region_selector": ".ldbz_con",
        "name_selector": "span a",
        "duty_selector": "span font",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "领导班子",
            "end_anchor": "内设机构",
            "include_selectors": [".ldbz_box", ".ldbz_con"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": None,
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
        },
        "risk_flag": "领导班子页使用.ldbz_con人物卡片；当前站点对自动新建浏览器标签页可能返回412或防护短页",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".ldbz_con",
                "name_selector": "span a",
                "duty_selector": "span font",
                "detail_link_selector": "",
                "content_scope": {
                    "start_anchor": "领导班子",
                    "end_anchor": "内设机构",
                    "include_selectors": [".ldbz_box", ".ldbz_con"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导班子页渲染DOM已包含全部领导姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(str(page_rule["leader_region_selector"])):
        name_node = card.select_one(str(page_rule["name_selector"]))
        duty_node = card.select_one(str(page_rule["duty_selector"]))
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = normalize_space(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.ldbz_con；name=span a；duty=span font",
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
    rule_id_value = "1328"
    main(rule_id_value)
