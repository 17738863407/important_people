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
    "rule_id": "2824",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "listing_link_selector": "div.link[link]",
    "listing_link_text": "领导简介",
    "leader_region_selector": "#er-content .er-box > div > p",
    "listing_timeout_seconds": 25,
    "risk_flag": "online会跟随页面脚本跳转至移动首页；需保留入口原始HTML，并从导航动态进入领导简介列表。",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _find_listing_url(html: str, final_url: str, page_rule: dict) -> str:
    """从权威入口页的机构导航中动态取得领导简介列表页。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = str(page_rule["listing_link_selector"])
    expected_text = str(page_rule["listing_link_text"])
    for node in soup.select(selector):
        if _clean_compact(node.get_text(" ", strip=True)) != expected_text:
            continue
        href = str(node.get("link", "")).strip()
        if href and not href.lower().startswith(("#", "javascript:", "mailto:")):
            return urljoin(final_url or str(page_rule.get("url", "")), href)
    raise ValueError("入口页未找到可验证的“领导简介”列表链接")


def _fetch_listing_page(listing_url: str, timeout_seconds: int) -> tuple[str, str]:
    """通过项目公共采集器读取领导简介列表页，保留统一失败链路。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(
        listing_url,
        strategy="raw_http",
        timeout=timeout_seconds,
    )
    return result.html, result.final_url or listing_url


def _split_person_row(node: object) -> tuple[str, str]:
    """按列表页连续空白分隔姓名与原始职务，不做任何语义补全。"""
    raw_text = str(node.get_text("", strip=True))
    parts = re.split(r"\s{2,}", raw_text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"人物行无法按连续空白分隔姓名与职务：{_clean_text(raw_text)}")
    name = _clean_compact(parts[0])
    evidence = _clean_text(parts[1]).replace("（兼）", "").replace("(兼)", "")
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
        raise ValueError(f"人物行姓名格式异常：{name}")
    if not evidence:
        raise ValueError(f"人物行缺少原始职务：{name}")
    return name, evidence


def _extract_detail_url(node: object, listing_url: str, source_url: str) -> str:
    """仅接受当前人物段落内可验证的一一对应链接。"""
    link = node.select_one("a[href]")
    href = str(link.get("href", "") if link else "").strip()
    if not href or href.lower().startswith(("#", "javascript:", "mailto:")):
        return ""
    candidate_url = urljoin(listing_url, href)
    excluded_urls = {listing_url.rstrip("/"), source_url.rstrip("/")}
    if candidate_url.rstrip("/") in excluded_urls:
        return ""
    return candidate_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """动态进入领导简介列表，并按页面段落原始顺序提取人物。"""
    listing_url = _find_listing_url(html, final_url, page_rule)
    timeout_seconds = int(page_rule["listing_timeout_seconds"])
    listing_html, listing_final_url = _fetch_listing_page(listing_url, timeout_seconds)
    soup = BeautifulSoup(listing_html, "html.parser")
    selector = str(page_rule["leader_region_selector"])
    person_nodes = list(soup.select(selector))
    if not person_nodes:
        raise ValueError(f"领导简介列表未命中人物段落：{selector}")

    rows: list[dict] = []
    seen_names: set[str] = set()
    source_url = str(page_rule.get("url", ""))
    for source_order, node in enumerate(person_nodes, start=1):
        name, evidence = _split_person_row(node)
        if name in seen_names:
            raise ValueError(f"领导简介列表出现重复姓名，需人工复核：{name}")
        seen_names.add(name)
        rows.append(
            {
                "order": str(source_order),
                "name": name,
                "duty": "",
                "detail_url": _extract_detail_url(node, listing_final_url, source_url),
                "evidence": evidence,
                "selector_summary": "入口页div.link[link]中的领导简介链接 -> #er-content .er-box > div > p",
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
