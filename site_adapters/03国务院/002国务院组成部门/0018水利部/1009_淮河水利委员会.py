from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1009",
    "page_type": "人物列表完整页",
    "structure_group": "hrc_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hrc_leader_cards_v2",
    "leader_region_selector": "#main_container .leader_cont1, #main_container .leader_cont2",
    "name_selector": ".con2",
    "duty_selector": ".con1",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#main_container"],
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
    "risk_flag": "首张leader_cont1卡片未设con2姓名节点，需从con1开头拆分；其余卡片使用con2/con1强字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_leader_cards",
    "locator": {
        "css": {
            "leader_region_selector": "#main_container .leader_cont1, #main_container .leader_cont2",
            "name_selector": ".con2",
            "duty_selector": ".con1",
            "detail_link_selector": "a[href]",
        },
        "api": {"enabled": False, "reason": "当前静态HTML委领导卡片直接提供姓名、职务和详情链接"},
        "migration": {
            "source": "legacy_business_source_and_stale_metadata_removed",
            "verified_status": "verified_current_raw_http",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def _parse_card(card: Tag) -> tuple[str, str] | None:
    name_node = card.select_one(".con2")
    duty_node = card.select_one(".con1")
    if name_node is not None and duty_node is not None:
        return re.sub(r"\s+", "", name_node.get_text(" ", strip=True)), _clean_text(
            duty_node.get_text(" ", strip=True)
        )
    text = _clean_text(card.get_text(" ", strip=True))
    match = re.fullmatch(r"([\u4e00-\u9fff·]{2,20})\s+(.+)", text)
    return (match.group(1), match.group(2)) if match else None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按委领导卡片DOM顺序解析两种卡片字段结构。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for card in soup.select("#main_container .leader_cont1, #main_container .leader_cont2"):
        parsed = _parse_card(card)
        if parsed is None:
            continue
        name, duty = parsed
        if not duty or name in seen_names:
            continue
        link_node = card.select_one("a[href]")
        detail_url = urljoin(final_url, link_node.get("href", "")) if link_node else ""
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
                selector_summary="leader_cont1/leader_cont2卡片内con2姓名、con1职务和a链接",
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
