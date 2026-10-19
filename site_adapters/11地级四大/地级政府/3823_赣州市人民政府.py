from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧市长之窗名单顺序进入详情页，提取标题中的姓名和具体职务。"""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    navigation = soup.select_one("#nav1")
    if navigation is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in navigation.select(":scope > li > a[href]"):
        name = clean_text(link.get("title") or link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "").strip()
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not href:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, href)
        detail = fetch_html_with_strategy(
            detail_url,
            strategy="requests",
            force_browser=False,
            timeout=30,
        )
        detail_soup = BeautifulSoup(detail.html, "html.parser")
        region = detail_soup.select_one(".list_li.zw_sz")
        heading_node = region.select_one("h2") if region else None
        heading = clean_text(heading_node.get_text(" ", strip=True) if heading_node else "")
        heading_match = re.fullmatch(r"(.+?)\s*[：:]\s*([\u3400-\u9fff·]{2,8})", heading)
        if heading_match is None or heading_match.group(2) != name:
            continue
        evidence = clean_text(heading_match.group(1)).rstrip("。．. ")
        rows.append({
            "name": name,
            "duty": evidence,
            "evidence": evidence,
            "detail_url": detail.final_url,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "左侧#nav1人物顺序及详情页.list_li.zw_sz标题职务",
        })
    return rows


PAGE_RULE = {
    "rule_id": "3823",
    "page_type": "市长之窗左侧人物列表转详情页",
    "load_mode": "静态HTML直出并逐详情请求",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_inline_ganzhou_government_profile_v2",
    "leader_region_selector": "#nav1",
    "name_selector": "#nav1 > li > a[href]",
    "duty_selector": ".list_li.zw_sz h2",
    "detail_link_selector": "#nav1 > li > a[href]",
    "detail_strategy": {"required": True, "mode": "dynamic_list_links", "max_detail_links": 20},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "左侧#nav1为完整人物顺序；姓名和具体职务须在对应详情页标题中相互校验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
