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


def is_duty(text: str) -> bool:
    return bool(re.search(r"党组|厅长|巡视员|纪检监察组|主任", clean_duty(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.gansu.gov.cn",
        "page_type": "人物表格页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_table_direct",
        "collector": "static_http",
        "parser": "page_gansu_science_leader_table_v1",
        "leader_region_selector": "table containing 甘肃省科学技术厅领导之窗",
        "name_selector": "two-column leader rows second td",
        "duty_selector": "two-column leader rows first td",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "甘肃省科学技术厅领导之窗",
            "end_anchor": "返回上级",
            "include_selectors": ["table"],
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
        },
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "table containing 甘肃省科学技术厅领导之窗",
                "name_selector": "two-column leader rows second td",
                "duty_selector": "two-column leader rows first td",
                "detail_link_selector": "",
                "content_scope": {
                    "start_anchor": "甘肃省科学技术厅领导之窗",
                    "end_anchor": "返回上级",
                    "include_selectors": ["table"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导之窗正文表格直接列出职务和姓名"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    leader_table = None
    for table in soup.select("table"):
        text = table.get_text(" ", strip=True)
        if "甘肃省科学技术厅领导之窗" in text:
            leader_table = table
            break
    if not leader_table:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for table_row in leader_table.select("tr"):
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in table_row.find_all(["td", "th"], recursive=False)]
        if len(cells) != 2:
            continue
        duty = clean_duty(cells[0])
        name = clean_name(cells[1])
        if name in seen_names or not is_name(name) or not is_duty(duty) or len(duty) > 80:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=leader table；fields=two-column tr td；detail_chain=0",
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
    rule_id_value = "1374"
    main(rule_id_value)
