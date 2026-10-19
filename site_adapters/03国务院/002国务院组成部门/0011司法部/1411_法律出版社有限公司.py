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
    "rule_id": "1411",
    "page_type": "人物列表完整页",
    "structure_group": "lawpress_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_lawpress_leader_cards_v2",
    "leader_region_selector": "ul.about_leader li",
    "name_selector": "h2 b",
    "duty_selector": "h2 span",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "公司领导",
        "end_anchor": "",
        "include_selectors": ["ul.about_leader"],
        "exclude_selectors": [".menu", ".aside_about", ".footer", "script", "style"],
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
    "risk_flag": "部分姓名含版面空格；公司领导卡片无人物独立详情链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_leader_cards",
    "locator": {
        "css": {"leader_region_selector": "ul.about_leader li", "name_selector": "h2 b", "duty_selector": "h2 span"},
        "api": {"enabled": False, "reason": "当前静态HTML公司领导卡片直接提供姓名和职务"},
        "migration": {
            "source": "legacy_business_source_adapter_path_and_entry_detail_removed",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按公司领导卡片DOM顺序提取姓名和职务强字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for item in soup.select("ul.about_leader li"):
        name_node = item.select_one("h2 b")
        duty_node = item.select_one("h2 span")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True)).strip("：:，,。.")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="ul.about_leader li内h2 b姓名与h2 span职务",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
