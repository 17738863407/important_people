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
    "rule_id": "0345",
    "page_type": "职务分组名单页",
    "structure_group": "csrd_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "csrd_current_leader_grouped_list_v1",
    "leader_region_selector": ".zrfl",
    "name_selector": "ul.fz a[href] p",
    "duty_selector": "strong",
    "detail_link_selector": "ul.fz a[href]",
    "content_scope": {
        "include_selectors": [".zrfl"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "ul.fz a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "姓名节点可能含零宽字符，站点TLS握手偶发失败",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _detail_url(final_url: str, entry_url: str, href: str) -> str:
    href = href.strip()
    candidate = urljoin(final_url, href)
    if (
        not href
        or href.startswith(("#", "javascript:", "mailto:"))
        or _normalize_url(candidate) == _normalize_url(entry_url)
    ):
        return ""
    return candidate


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按职务标题和相邻人物列表的DOM顺序提取主任会议成员。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zrfl")
    if region is None:
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[tuple[str, str]] = set()
    current_duty = ""
    for node in region.find_all(["strong", "ul"], recursive=False):
        if node.name == "strong":
            current_duty = _clean_text(node.get_text(" ", strip=True))
            continue
        if node.name != "ul" or not current_duty:
            continue
        for anchor in node.select("a[href]"):
            name_node = anchor.select_one("p")
            if name_node is None:
                continue
            name = _clean_text(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            key = (name, current_duty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=entry_url,
                    name=name,
                    duty=current_duty,
                    detail_url=_detail_url(
                        final_url, entry_url, anchor.get("href", "")
                    ),
                    evidence=current_duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary=".zrfl直接子节点：strong + ul.fz a[href] p",
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
