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
    "rule_id": "2064",
    "page_type": "人物列表完整页",
    "structure_group": "ouchn_school_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ouchn_school_leader_cards_v1",
    "leader_region_selector": ".page_content .sub_011",
    "name_selector": "ul > li .title",
    "duty_selector": "ul > li .tip",
    "detail_link_selector": "ul > li > a[href]",
    "content_scope": {
        "include_selectors": [".page_content .sub_011"],
        "exclude_selectors": [".info"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_link_selector": "ul > li > a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "卡片含隐藏简介和无效井号链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """合并页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按学校领导卡片的DOM顺序提取姓名与原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".page_content .sub_011")
    if region is None:
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    for item in region.select("ul > li"):
        name_node = item.select_one(".title")
        duty_node = item.select_one(".tip")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not duty:
            continue

        detail_url = ""
        anchor = item.select_one(":scope > a[href]")
        if anchor is not None:
            href = anchor.get("href", "").strip()
            candidate = urljoin(final_url, href)
            if (
                href
                and not href.startswith(("#", "javascript:", "mailto:"))
                and _normalize_url(candidate) != _normalize_url(entry_url)
            ):
                detail_url = candidate

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
                selector_summary=".sub_011 ul > li: .tip + .title",
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
