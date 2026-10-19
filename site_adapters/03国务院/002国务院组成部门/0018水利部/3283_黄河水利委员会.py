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


PAGE_RULE = {
    "rule_id": "3283",
    "page_type": "人物列表完整页",
    "structure_group": "yrcc_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yrcc_leader_cards_v2",
    "leader_region_selector": ".hw_leader_content",
    "name_selector": "a[href] p",
    "duty_selector": "a[href] span",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "黄委领导",
        "end_anchor": "",
        "include_selectors": [".hw_leader_content"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 10,
    },
    "risk_flag": "区域首链接为领导栏目入口且无p/span；只解析同时具备姓名p与职务span的人物卡片，不补写机构前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_leader_cards",
    "locator": {
        "css": {
            "leader_region_selector": ".hw_leader_content",
            "name_selector": "a[href] p",
            "duty_selector": "a[href] span",
            "detail_link_selector": "a[href]",
        },
        "api": {"enabled": False, "reason": "当前静态HTML黄委领导卡片直接提供姓名、职务和详情链接"},
        "migration": {
            "source": "legacy_organization_prefix_rewrite_and_business_source_removed",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按黄委领导卡片DOM顺序提取姓名、原始职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".hw_leader_content")
    if region is None:
        return []
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]"):
        name_node = link.select_one("p")
        duty_node = link.select_one("span")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True).replace("\u3000", " "))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not duty or name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".hw_leader_content人物a内p姓名与span职务",
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
