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
    "rule_id": "2500",
    "page_type": "多人物详情合并页",
    "structure_group": "sichuan_water_leader_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "leader_region_selector": "div.l-img > a[href], ul.ldcy a[href]",
    "detail_content_selector": "div.l-img",
    "detail_fetch_mode": "online",
    "confidence": "high",
}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析四川省水利厅在线页面中的领导链接。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    leader_selector = str(page_rule["leader_region_selector"])
    detail_selector = str(page_rule["detail_content_selector"])
    detail_fetch_mode = str(page_rule["detail_fetch_mode"])

    for link in soup.select(leader_selector):
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("#", "javascript:", "mailto:")):
            raise RuntimeError("领导人物链接为空或不是可访问详情页")
        detail_url = urljoin(final_url, href)
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            raise RuntimeError("领导人物链接错误地指向机构入口页")
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        source_text = _clean_text(link.get_text(" ", strip=True))
        name_match = re.search(r"[\u3400-\u9fff·]{2,4}$", source_text)
        if not name_match:
            raise RuntimeError(f"无法从领导链接文本取得姓名：{source_text}")
        name = name_match.group(0)

        detail_result = fetch_html_with_strategy(detail_url, detail_fetch_mode)
        if detail_result.status_code and detail_result.status_code != 200:
            raise RuntimeError(f"领导详情页返回 HTTP {detail_result.status_code}：{detail_url}")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        detail_node = detail_soup.select_one(detail_selector)
        detail_text = _clean_text(detail_node.get_text(" ", strip=True)) if detail_node else ""
        if not detail_text.endswith(name):
            raise RuntimeError(f"领导详情字段与入口姓名不一致：{name} / {detail_text}")
        duty = detail_text[: -len(name)].strip()
        if not duty:
            raise RuntimeError(f"领导详情页缺少原始职务：{name}")

        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "selector_summary": f"{leader_selector} -> {detail_selector}",
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
