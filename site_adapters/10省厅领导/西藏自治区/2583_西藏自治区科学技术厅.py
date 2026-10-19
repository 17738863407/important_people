from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2583',
 'domain': 'sti.xizang.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_xizang_science_online_details_v1',
 'leader_region_selector': '.lzy-info-bg领导简介列表及在线详情',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': 'html > body > div.lzy-info-bg',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导简介列表和详情页均为静态 HTML'},
             'migration': {'source': 'legacy_page_rule',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(rf"{re.escape(name)}\s*\(\s*(?P<duty>[^)）]+)\s*[)）]", text)
    duty = _clean_text(match.group("duty")) if match else ""
    return duty, text[:180]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".lzy-info-bg") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    for link in box.find_all("a", href=True):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        item_text = _clean_text(link.parent.get_text(" ", strip=True) if link.parent else "")
        if not re.search(r"20\d{2}-\d{2}-\d{2}", item_text):
            continue
        if name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        try:
            response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            continue
        duty, evidence = _extract_duty(response.text, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_xizang_science_online_details_v1",
                "selector_summary": ".lzy-info-bg带日期领导链接；详情姓名括号职务",
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
