from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2622',
 'domain': 'swt.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_guizhou_commerce_online_detail_v2',
 'leader_region_selector': 'html > body.ScrollStyle > div.wrap:nth-of-type(9) > div.Main.aBox:nth-of-type(2) > div.lby > div.lbycon:nth-of-type(2) > div.RightBox.aBox:nth-of-type(2) > div.ldzcBox',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href*="/ldzc/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
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
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body.ScrollStyle > div.wrap:nth-of-type(9) > '
                                               'div.Main.aBox:nth-of-type(2) > div.lby > div.lbycon:nth-of-type(2) > '
                                               'div.RightBox.aBox:nth-of-type(2) > div.ldzcBox',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href*="/ldzc/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导之窗目录和详情页均为静态 HTML'},
             'migration': {'source': 'sequential_static_html_builder', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _fetch_detail_html(detail_url: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def _extract_detail(detail_html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"姓\s*名：\s*(?P<name>[\u4e00-\u9fff]{2,4})\s+担任职务：\s*(?P<duty>.+?)\s+领导分工：", text)
    if not match:
        return "", "", ""
    duty = _clean_text(match.group("duty"))
    return match.group("name"), duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        name = _clean_text(link.get_text(" ", strip=True))
        href = link.get("href") or ""
        detail_url = urljoin(source_url, href)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or not re.search(r"/zwgk/ldzc/\d{6}/t\d+_\d+\.html(?:$|[?#])", detail_url)
        ):
            continue
        if name in seen:
            continue
        try:
            detail_name, duty, evidence = _extract_detail(_fetch_detail_html(detail_url))
        except Exception:
            continue
        if detail_name:
            name = detail_name
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_guizhou_commerce_online_detail_v2",
                "selector_summary": "领导之窗链接；详情姓 名/担任职务字段",
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
