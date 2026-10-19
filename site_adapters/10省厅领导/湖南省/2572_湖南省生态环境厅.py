from __future__ import annotations

import re
import sys
from urllib.parse import urljoin, urlparse
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2572',
 'domain': 'sthjt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_hunan_ecology_online_details_v1',
 'leader_region_selector': '.main机构领导列表',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.main:nth-of-type(5)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '机构领导列表和详情页均为静态 HTML'},
             }}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_duty(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    main = soup.select_one(".main") or soup.body or soup
    text = _clean_text(main.get_text(" ", strip=True))
    match = re.search(r"职\s*务：\s*(?P<duty>.+?)\s*工作职责：", text)
    if not match:
        match = re.search(r"职\s*务：\s*(?P<duty>[^。；;]{2,100})", text)
    duty = _clean_text(match.group("duty")) if match else ""
    return duty, text[:180]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".main") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    for item in main.find_all("li"):
        text = _clean_text(item.get_text(" ", strip=True))
        match = re.match(r"(?P<name>[\u4e00-\u9fff]{2,4})\s+20\d{2}-\d{2}-\d{2}$", text)
        link = item.find("a", href=True)
        if not (match and link):
            continue
        name = match.group("name")
        if name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        if urlparse(detail_url).netloc.lower() != urlparse(final_url).netloc.lower():
            continue
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=60,
        )
        detail_html = detail_result.html
        duty, _ = _extract_duty(detail_html)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".main姓名日期列表；详情职务字段",
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
