from __future__ import annotations

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
    "rule_id": "0773",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_hightech_leader_list_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "leader_region_selector": ".sideright #contentList",
    "detail_link_selector": ":scope > li > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_content_selector": ".main01-rcr",
        "detail_name_selector": ".main01-rcr2",
        "detail_duty_selector": ".main01-rcr1",
        "max_detail_links": 20,
    },
    "risk_flag": "职务为详情页独立字段，基本信息和分工不得混入依据说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口列表顺序访问详情页并读取独立姓名、职务字段。"""
    from crawler_core.fetcher import fetch_by_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for order, link in enumerate(soup.select(".sideright #contentList > li > a[href]"), start=1):
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_by_requests(detail_url)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        name_node = detail_soup.select_one(".main01-rcr2")
        duty_node = detail_soup.select_one(".main01-rcr1")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if not name or not duty:
            raise RuntimeError(f"详情页姓名或职务字段为空：{detail_result.final_url}")
        rows.append(
            {
                "order": str(order),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_haikou_hightech_leader_list_detail_v1",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
