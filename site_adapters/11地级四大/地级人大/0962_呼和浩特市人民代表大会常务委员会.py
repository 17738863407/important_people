from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0962",
    "page_type": "人物列表完整页",
    "structure_group": "hohhot_renda_visible_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hohhot_renda_visible_leader_cards_v1",
    "leader_region_selector": ".leader .leaderRight .lrDetail",
    "name_selector": "ul > li > a[href] span:not(.zw)",
    "duty_selector": "ul > li > a[href] span.zw",
    "detail_link_selector": "ul > li > a[href]",
    "content_scope": {
        "include_selectors": [".leader .leaderRight .lrDetail"],
        "exclude_selectors": [".leaderLeft"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "ul > li > a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "隐藏leaderLeft含重复人物，必须只解析可见leaderRight卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value)).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """仅解析可见领导卡片中的明确职务和姓名节点。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader .leaderRight .lrDetail")
    if region is None:
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for anchor in region.select("ul > li > a[href]"):
        duty_node = anchor.select_one("span.zw")
        if duty_node is None:
            continue
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        name_node = duty_node.find_next_sibling("span")
        if name_node is None:
            continue
        name = _clean_name(name_node.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        href = anchor.get("href", "").strip()
        detail_url = urljoin(final_url, href)
        if (
            not href
            or href.startswith(("#", "javascript:", "mailto:"))
            or _normalize_url(detail_url) == _normalize_url(entry_url)
        ):
            detail_url = ""
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".leaderRight .lrDetail ul > li：span.zw + 姓名span",
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
