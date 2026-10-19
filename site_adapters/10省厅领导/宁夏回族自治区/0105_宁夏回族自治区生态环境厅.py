from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0105',
 'domain': 'sthjt.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_nx_sthjt_title_links_v1',
 'leader_region_selector': 'a[title*=同志]',
 'name_selector': 'title before 同志',
 'duty_selector': 'title parentheses',
 'detail_link_selector': 'a[href]',
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
 'locator': {'css': {'leader_region_selector': 'a[title*=同志]',
                     'name_selector': 'title before 同志',
                     'duty_selector': 'title parentheses',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面采集'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析宁夏回族自治区生态环境厅领导链接标题。"""
    import re
    from urllib.parse import urljoin, urlparse

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select('a[title*="同志"]'):
        title = link.get("title", "").strip()
        match = re.search(r"^([\u4e00-\u9fff]{2,4})同志[（(](.+?)[）)]$", title)
        if not match:
            continue
        name = match.group(1).strip()
        duty = match.group(2).strip()
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        page_url = str(page_rule.get("url", "")) or final_url
        detail_url = urljoin(page_url, link.get("href", "").strip())
        detail = urlparse(detail_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not detail.path.lower().endswith((".html", ".htm"))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": 'a[title*="同志"] title 姓名/括号职务',
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
