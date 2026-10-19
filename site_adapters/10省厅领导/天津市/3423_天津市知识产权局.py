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


PAGE_RULE = {
    "rule_id": "3423",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_ip_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_ip_leader_cards_v1",
    "leader_region_selector": "ul.list4",
    "name_selector": "ul.list4 > li p:first-of-type b",
    "duty_selector": "ul.list4 > li第二个p中移除职务标签后的文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["ul.list4 > li"],
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
        "max_detail_links": 50,
    },
    "risk_flag": "卡片外层链接均为javascript:void(0)，不是独立人物详情页；职务应取明确标签后的文本节点",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.list4",
            "name_selector": "> li p:first-of-type b",
            "duty_selector": "> li p:nth-of-type(2)移除b标签后的文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个人物卡片",
                "end_anchor": "末个人物卡片",
                "include_selectors": ["ul.list4 > li"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML卡片直接提供明确姓名与职务字段",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def _extract_duty(paragraph: object) -> str:
    copied_paragraph = BeautifulSoup(str(paragraph), "html.parser").select_one("p")
    if copied_paragraph is None:
        return ""
    label = copied_paragraph.select_one("b")
    if label is None or re.sub(r"\s+", "", label.get_text(" ", strip=True)) != "职务":
        return ""
    label.decompose()
    return _clean_text(copied_paragraph.get_text(" ", strip=True)).strip("：: ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见领导卡片DOM顺序提取姓名与明确职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.list4 > li"):
        paragraphs = item.select("p")
        if len(paragraphs) < 2:
            continue
        name_node = paragraphs[0].select_one("b")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _extract_duty(paragraphs[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_ip_leader_cards_v1",
                "selector_summary": "ul.list4人物卡片；首段b姓名；第二段职务标签后文本",
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
