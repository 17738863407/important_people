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

PAGE_RULE = {'rule_id': '2634',
 'domain': 'swt.shanxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'raw_http',
 'parser': 'custom_shanxi_commerce_leader_sidebar_v1',
 'leader_region_selector': '.Lst02领导分工链接',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.Lst02 li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': '.Lst02',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.Lst02 li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    source_url = str(page_rule.get("url") or final_url)
    parsed_source = urlparse(source_url)
    site_root = f"{parsed_source.scheme}://{parsed_source.netloc}/"
    home_result = fetch_html_with_strategy(site_root, strategy="raw_http", timeout=60)
    html = home_result.html
    final_url = home_result.final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(".Lst02 li a[href]"):
        span = link.select_one("span")
        if not span:
            continue
        name = _clean_text(span.get_text(" ", strip=True))
        full_text = _clean_text(link.get_text(" ", strip=True))
        duty = _clean_text(full_text.replace(name, "", 1))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(final_url, link.get("href") or ""),
                "evidence": duty,
                "parser": "custom_shanxi_commerce_leader_sidebar_v1",
                "selector_summary": ".Lst02领导链接span姓名及余下职务",
                "order": str(len(rows) + 1),
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
