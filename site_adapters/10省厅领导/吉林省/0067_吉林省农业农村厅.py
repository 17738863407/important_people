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

PAGE_RULE = {'rule_id': '0067',
 'domain': 'agri.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'page_inline_jilin_agri_leader_tabs_v1',
 'leader_region_selector': 'div.tab_news_top_hd.ld2024ul li',
 'name_selector': 'b a[title]',
 'duty_selector': 'p',
 'detail_link_selector': 'div.tab_news_top_hd.ld2024ul li b a[href]',
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
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.tab_news_top_hd.ld2024ul li',
                     'name_selector': 'b a[title]',
                     'duty_selector': 'p',
                     'detail_link_selector': 'div.tab_news_top_hd.ld2024ul li b a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.tab_news_top_hd.ld2024ul li；"
        "name=b a[title]；duty=p；detail=div.tab_news_top_hd.ld2024ul li b a[href]；api_enabled=False"
    )
    for item in soup.select("div.tab_news_top_hd.ld2024ul li"):
        name_node = item.select_one("b a[title]")
        if name_node is None:
            # 在线页面已移除 title 属性，仍限定在原 b 姓名链接节点内兼容。
            name_node = item.select_one("b a[href]")
        duty_node = item.select_one("p")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), name_node.get("href", ""))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(final_url).netloc.lower()
        real_person_page = bool(re.search(r"/gk/tld/tld/[a-z0-9_-]+/$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
