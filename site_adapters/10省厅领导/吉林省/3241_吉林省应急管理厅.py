from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3241',
 'domain': 'yjt.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_jilin_emergency_leader_v1',
 'leader_region_selector': 'ul.yjgl-top-ul > li',
 'name_selector': '.yjgl-dd01',
 'duty_selector': 'b',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.box-w1200:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析吉林省应急管理厅省厅领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.yjgl-top-ul > li"):
        name_node = item.select_one(".yjgl-dd01")
        duty_node = item.select_one("b")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text("", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        link = item.select_one("a[href]")
        detail_url = urljoin(final_url or page_rule["url"], link.get("href", "")) if link else ""
        same_host = urlparse(detail_url).netloc.lower() == urlparse(final_url).netloc.lower()
        real_person_page = bool(re.search(r"/jggk/stld/[a-z0-9_-]+/\d{6}/t\d+_\d+\.html$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "ul.yjgl-top-ul li .yjgl-dd01 + b",
            }
        )
    return rows


if __name__ == "__main__":
    main()
