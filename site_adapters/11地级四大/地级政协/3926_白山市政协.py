from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3926",
    "page_type": "分栏目领导页面",
    "structure_group": "baishan_cppcc_category_pages_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML分栏目",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "category_pages",
    "collector": "raw_http",
    "parser": "page_inline_baishan_cppcc_categories_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ldzc",
    "name_selector": ".ldzc_ul p",
    "duty_selector": ".ldzc h3",
    "detail_link_selector": ".ldzc_ul a[href]",
    "timeout_seconds": 35,
    "risk_flag": "主席、副主席、秘书长分属三个栏目；入口仅显示主席栏目",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_category(category_html: str, category_url: str, page_rule: dict) -> list[dict]:
    """解析单个领导职务栏目。"""
    soup = BeautifulSoup(category_html, "lxml")
    region = soup.select_one(".ldzc")
    if region is None:
        return []
    duty_node = region.select_one("h3")
    duty = clean_name(duty_node.get_text(" ", strip=True) if duty_node else "")
    if duty not in {"主席", "副主席", "秘书长"}:
        return []

    pairs: list[tuple[object, object]] = []
    cards = region.select(".ldzc_ul > li")
    if cards:
        for card in cards:
            pairs.append((card.select_one("p"), card.select_one("a[href]")))
    else:
        container = region.select_one(".ldzc_ul")
        if container is not None:
            pairs.append((container.find("p", recursive=False), container.find("a", href=True, recursive=False)))

    rows: list[dict] = []
    for name_node, link in pairs:
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        href = clean_text(link.get("href")) if link else ""
        detail_url = urljoin(category_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if urlparse(detail_url).scheme not in {"http", "https"}:
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".ldzc h3职务与.ldzc_ul人物卡片",
            }
        )
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口栏目导航顺序抓取三个领导栏目。"""
    import requests

    base_url = final_url or page_rule["url"]
    soup = BeautifulSoup(html, "lxml")
    category_links: list[str] = []
    seen_urls: set[str] = set()
    for link in soup.select(".tit_ul a[href]"):
        label = clean_name(link.get_text(" ", strip=True))
        category_url = urljoin(base_url, clean_text(link.get("href")))
        if label not in {"主席", "副主席", "秘书长"} or category_url in seen_urls:
            continue
        seen_urls.add(category_url)
        category_links.append(category_url)

    session = requests.Session()
    session.trust_env = False
    rows: list[dict] = []
    seen_names: set[str] = set()
    for category_url in category_links:
        response = session.get(
            category_url,
            timeout=int(page_rule["timeout_seconds"]),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        for row in parse_category(response.text, response.url or category_url, page_rule):
            if row["name"] in seen_names:
                continue
            seen_names.add(row["name"])
            rows.append(row)

    if not rows:
        raise RuntimeError("主席、副主席、秘书长栏目均未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
