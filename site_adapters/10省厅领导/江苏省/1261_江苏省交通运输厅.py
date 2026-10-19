from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1261',
 'domain': 'jtyst.jiangsu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'playwright',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_jiangsu_transport_leader_links_v1',
 'leader_region_selector': 'a[href*="/art/"][href*="art_60017"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#barrierfree_container',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面包含领导分工链接列表'}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    if not html:
        from crawler_core.fetcher import fetch_html_with_strategy

        fetched = fetch_html_with_strategy(
            str(page_rule["url"]), strategy="extract", force_browser=True, timeout=30
        )
        html = fetched.html
        final_url = fetched.final_url

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/art/"][href*="art_60017"]'):
        text = clean_text(link.get_text(" ", strip=True))
        if "：" not in text:
            continue
        name, duty = [clean_text(part) for part in text.split("：", 1)]
        name = name.replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(str(page_rule.get("url", "")) or final_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(str(page_rule.get("url", "")) or final_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or not re.search(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_60017_\d+\.html$", detail.path)
        ):
            detail_url = ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "领导分工链接文本姓名冒号职务",
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
