from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2497',
 'domain': 'slt.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_inner_mongolia_water_leader_colleagues_v1',
 'leader_region_selector': '.xy_LingDao .ld h3, .xy_LingDao .ts p',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.xy_LingDao .ts p a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.xy_LingDao .ts p a[href]',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.xy_LingDao .ld h3, .xy_LingDao .ts p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.xy_LingDao .ts p a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def _clean_duty(value: str) -> str:
    return _clean_text(value).rstrip(":：")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析内蒙古自治区水利厅领导详情页左侧领导和同事列表。"""
    page_url = str(page_rule.get("url", final_url))
    content_url = final_url or page_url
    soup = BeautifulSoup(html, "html.parser")
    for _ in range(5):
        if soup.select_one(".xy_LingDao") is not None:
            break
        redirect_matches = re.findall(r"window\.location\.replace\(['\"]([^'\"]+)['\"]\)", html)
        if not redirect_matches:
            break
        redirect_url = urljoin(content_url, redirect_matches[-1])
        request = Request(redirect_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
            content_url = response.geturl()
        soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_record(name: str, duty: str, detail_url: str) -> None:
        name = _clean_text(name)
        duty = _clean_duty(duty)
        if not name or not duty:
            return
        key = (name, duty)
        if key in seen:
            return
        seen.add(key)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
            }
        )

    current = soup.select_one(".xy_LingDao .ld h3")
    if current is not None:
        name_node = current.select_one(".fly_title_ldxm")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        if name_node is not None:
            name_node.extract()
        duty = current.get_text(" ", strip=True)
        add_record(name, duty, content_url)

    for item in soup.select(".xy_LingDao .ts p"):
        duty_node = item.select_one("i")
        link = item.select_one("a[href]")
        if duty_node is None or link is None:
            continue
        add_record(
            link.get_text(" ", strip=True),
            duty_node.get_text(" ", strip=True),
            urljoin(content_url, link.get("href", "")),
        )
    return records


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
