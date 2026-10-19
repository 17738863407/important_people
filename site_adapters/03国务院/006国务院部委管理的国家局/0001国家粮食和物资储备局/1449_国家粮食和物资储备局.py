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
    return normalize_space(text).strip(" ：:，,。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def is_leader_duty(text: str) -> bool:
    return bool(re.search(r"(书记|局长|巡视员|总工程师)", clean_duty(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "www.lswz.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_cards_direct",
        "collector": "static_http",
        "parser": "page_national_grain_leader_cards_v1",
        "leader_region_selector": ".jggk-box .ld-list",
        "name_selector": ".ld-tit a",
        "duty_selector": ".ld-zw",
        "detail_link_selector": ".ld-tit a[href]",
        "content_scope": {
            "start_anchor": "局领导",
            "end_anchor": "司局子站",
            "include_selectors": [".jggk-box .ld-list"],
            "exclude_selectors": [".zz-list", ".gk-box", ".footer", "script", "style"],
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
        "risk_flag": "online_leader_cards_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist_allow_chief_engineer",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".jggk-box .ld-list",
                "name_selector": ".ld-tit a",
                "duty_selector": ".ld-zw",
                "detail_link_selector": ".ld-tit a[href]",
                "content_scope": {
                    "start_anchor": "局领导",
                    "end_anchor": "司局子站",
                    "include_selectors": [".jggk-box .ld-list"],
                    "exclude_selectors": [".zz-list", ".gk-box", ".footer", "script", "style"],
                },
            },
            "api": {"enabled": False, "reason": "机构设置页局领导模块直接列出姓名和职务"},
            "migration": {
                "source": "manual_rewrite_existing_adapter",
                "verified_status": "pending",
                "behavior_changed": True,
            },
        },
    }


def append_row(rows: list[dict[str, str]], seen_names: set[str], name: str, duty: str, detail_url: str, page_rule: dict) -> None:
    clean = clean_name(name)
    duty_text = clean_duty(duty)
    if not is_name(clean) or not is_leader_duty(duty_text) or clean in seen_names:
        return
    seen_names.add(clean)
    rows.append(
        {
            "name": clean,
            "duty": duty_text,
            "detail_url": detail_url,
            "evidence": duty_text,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "strategy=custom_parse_page；region=.jggk-box .ld-list；fields=.ld-tit a + .ld-zw；detail_chain=0",
        }
    )


def parse_leader_block(block: BeautifulSoup, final_url: str, page_rule: dict, rows: list[dict[str, str]], seen_names: set[str]) -> None:
    direct_title = block.select_one(":scope > .ld-tit a[href]")
    direct_duty = block.select_one(":scope > .ld-zw")
    if direct_title is not None and direct_duty is not None:
        append_row(
            rows,
            seen_names,
            direct_title.get_text(" ", strip=True),
            direct_duty.get_text(" ", strip=True),
            urljoin(final_url, direct_title.get("href", "")),
            page_rule,
        )

    for item in block.select("dl dd"):
        title = item.select_one(".ld-tit a[href]")
        duty = item.select_one(".ld-zw")
        if title is None or duty is None:
            continue
        append_row(
            rows,
            seen_names,
            title.get_text(" ", strip=True),
            duty.get_text(" ", strip=True),
            urljoin(final_url, title.get("href", "")),
            page_rule,
        )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".jggk-box")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for block in region.select(".ld-list"):
        parse_leader_block(block, final_url, page_rule, rows, seen_names)
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
    rule_id_value = "1449"
    main(rule_id_value)
