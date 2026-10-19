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

PAGE_RULE = {'rule_id': '1216',
 'domain': 'jswater.jiangsu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'force_browser': True,
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'playwright',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_jiangsu_water_list_text_v1',
 'leader_region_selector': "[id='367677'] li a[href]",
 'name_selector': '',
 'duty_selector': '',
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
                     'max_detail_links': 0},
 'confidence': 'high',
 'risk_flag': '普通HTTP请求命中云防护页，必须完成浏览器降级后解析#367677领导列表',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': "[id='367677'] li a[href]",
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def parse_leader_text(value: str) -> tuple[str, str]:
    """拆分“姓名 + 多空白 + 职务”。"""
    text = normalize_space(value)
    match = re.match(r"^([\u4e00-\u9fa5]{2,4})\s+(.+)$", text)
    if not match:
        return "", ""
    name, duty = match.groups()
    return name, duty.rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江苏省水利厅领导分工列表。"""
    if not html:
        from crawler_core.fetcher import fetch_html_with_strategy

        fetched = fetch_html_with_strategy(
            str(page_rule["url"]), strategy="extract", force_browser=True, timeout=30
        )
        html = fetched.html
        final_url = fetched.final_url

    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=find(id='367677') li a[href]；pattern=姓名+空白+职务"
    box = soup.find(id="367677")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in box.select("li a[href]") if box else []:
        raw_text = link.get_text(" ", strip=True)
        name, duty = parse_leader_text(raw_text)
        if not name or not duty or name in seen:
            continue
        detail_url = urljoin(page_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not re.search(r"/col/col\d+/index\.html$", detail.path)
        ):
            detail_url = ""
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
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
