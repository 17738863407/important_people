from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2495',
 'domain': 'slt.jl.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_jilin_water_detail_sidebar_v1',
 'leader_region_selector': '.zhuanti_box li > a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '列表页仅姓名，使用在线详情页侧栏补职务',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.zhuanti_box li > a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 列表和详情侧栏在线解析'}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _fetch_detail(detail_url: str) -> str:
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析吉林省水利厅详情页侧栏姓名与职务循环。"""
    list_soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    detail_urls: dict[str, str] = {}
    names: set[str] = set()
    first_detail_url = ""
    for link in list_soup.select(".zhuanti_box li > a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(final_url or source_url, href)
        same_host = urlparse(detail_url).netloc.lower() == urlparse(source_url).netloc.lower()
        real_person_page = bool(re.search(r"/zw/tzzc/[a-z0-9_-]+/$", urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        names.add(name)
        detail_urls[name] = detail_url
        if not first_detail_url:
            first_detail_url = detail_url

    page_html = _fetch_detail(first_detail_url) if first_detail_url else ""
    if not page_html:
        return []

    soup = BeautifulSoup(page_html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    lines = [_clean_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        if line not in names or line in seen:
            continue
        if index + 3 >= len(lines) or lines[index + 1] != "简介" or lines[index + 2] != "活动":
            continue
        duty = lines[index + 3]
        if not any(keyword in duty for keyword in ("厅长", "党组", "局长", "组长")):
            continue
        seen.add(line)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": line,
                "duty": duty,
                "detail_url": detail_urls.get(line, ""),
                "evidence": duty,
                "parser": "custom_jilin_water_detail_sidebar_v1",
                "selector_summary": "在线详情侧栏；姓名/简介/活动/职务循环",
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
