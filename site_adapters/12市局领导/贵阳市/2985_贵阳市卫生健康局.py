from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2985",
    "page_type": "人物目录详情页",
    "structure_group": "guiyang_health_leader_table_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "directory_detail",
    "collector": "static_http",
    "parser": "guiyang_health_leader_table_detail_v1",
    "leader_region_selector": ".zfxxgk_zdgkc > ul[bf-region-type='4'] > li",
    "name_selector": "a[href]",
    "duty_selector": "",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "页面脚本会把 online 采集误导向政务服务登录页，须保留原始 HTTP 响应",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写语义内容。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _extract_detail_url(href: str, final_url: str) -> str:
    """校验当前列表项动态提供的领导详情地址。"""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/zfxxgk_500627/fdzdgknr/jgjj/jgld2/\d{6}/t\d+_\d+\.html", detail.path):
        return ""
    return detail_url


def _extract_labeled_value(soup: BeautifulSoup, label: str) -> str:
    """按详情表格的明确字段标签取得相邻值单元格。"""
    for row in soup.select("#Zoom table tr"):
        cells = row.find_all("td", recursive=False)
        for index, cell in enumerate(cells[:-1]):
            cell_label = _clean_text(cell.get_text(" ", strip=True)).rstrip("：:")
            if cell_label == label:
                return _clean_text(cells[index + 1].get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表顺序在线读取每个领导详情页的姓名与担任职务字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    list_items = soup.select(page_rule["leader_region_selector"])
    if not list_items:
        raise RuntimeError("机构领导列表选择器未命中")

    records: list[object] = []
    seen_detail_urls: set[str] = set()
    for source_order, item in enumerate(list_items, start=1):
        link = item.select_one(page_rule["detail_link_selector"])
        list_name = _clean_text(link.get_text(" ", strip=True)) if link else ""
        if not re.fullmatch(r"[一-鿿·]{2,8}", list_name):
            raise RuntimeError(f"第 {source_order} 个列表项姓名无效：{list_name or '空'}")

        detail_url = _extract_detail_url(str(link.get("href", "")) if link else "", final_url)
        if not detail_url or detail_url in seen_detail_urls:
            raise RuntimeError(f"第 {source_order} 个列表项详情链接无效或重复")
        seen_detail_urls.add(detail_url)

        detail_result = fetch_by_raw_requests(detail_url, timeout=60)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        detail_name = _extract_labeled_value(detail_soup, "姓名")
        duty = _extract_labeled_value(detail_soup, "担任职务")
        if detail_name != list_name:
            raise RuntimeError(
                f"第 {source_order} 个详情页姓名不一致：列表={list_name}，详情={detail_name or '空'}"
            )
        if not duty:
            raise RuntimeError(f"第 {source_order} 个详情页未取得担任职务：{detail_url}")

        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=list_name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
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
