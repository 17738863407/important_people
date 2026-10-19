from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0809",
    "page_type": "人物列表与详情同页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_parse_page",
    "leader_region_selector": 'a[href*="/zwgk/ldzc/"][href$=".html"]',
    "name_selector": 'a[href*="/zwgk/ldzc/"][href$=".html"]',
    "duty_selector": ".name .p2",
    "detail_link_selector": 'a[href*="/zwgk/ldzc/"][href$=".html"]',
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "入口默认展示首位领导详情，同时包含全体领导导航；必须按导航顺序逐页验证",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "仅处理领导之窗路径下以.html结尾的人物链接；职务只取详情.name .p2明确字段，排除领导分工。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导导航原序抓取独立详情，并提取明确职务字段。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    selector = 'a[href*="/zwgk/ldzc/"][href$=".html"]'
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(selector):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, "requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        description = detail_soup.select_one('meta[name="Description"]')
        description_text = str(description.get("content", "")) if description else ""
        if name not in description_text:
            raise ValueError(f"领导详情简介与列表姓名不一致：{name}")
        duty = ""
        for duty_node in detail_soup.select(".name .p2"):
            candidate = re.sub(r"[\s\u3000\xa0]+", "", duty_node.get_text(" ", strip=True))
            if candidate:
                duty = candidate
                break
        if not duty:
            raise ValueError(f"领导详情缺少明确职务字段：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "parser": "page_parse_page",
                "selector_summary": "列表=领导之窗人物导航；详情职务=.name .p2",
            }
        )
    if not rows:
        raise ValueError("领导之窗未发现可验证人物链接")
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
