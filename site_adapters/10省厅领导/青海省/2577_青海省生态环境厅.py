from __future__ import annotations

import re
import sys
import urllib.request
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2577',
 'domain': 'sthjt.qinghai.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_qinghai_ecology_ldhd_online_v1',
 'leader_region_selector': '.scroll_main领导之窗及ldhd在线详情',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
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
 'locator': {'css': {'leader_region_selector': 'html > body > div.scroll_main',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导之窗列表和ldhd子页均为静态 HTML'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _fetch_online_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_duty(detail_html: str, display_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    before_intro = text.split(" 领导简介 ", 1)[0]
    duty = ""
    pos = before_intro.rfind(display_name)
    if pos >= 0:
        duty = _clean_text(before_intro[pos + len(display_name):])
    if not duty:
        compact = _compact_name(display_name)
        compact_text = before_intro.replace(" ", "")
        pos = compact_text.rfind(compact)
        if pos >= 0:
            duty = _clean_text(compact_text[pos + len(compact):])
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".scroll_main") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    for link in box.find_all("a", href=True):
        display_name = _clean_text(link.get_text(" ", strip=True))
        if display_name == "领导之窗":
            continue
        name = _compact_name(display_name)
        if not name or name in seen:
            continue
        detail_url = urljoin(page_rule["url"], (link.get("href") or "").rstrip("/") + "/ldhd/")
        try:
            duty, evidence = _extract_duty(_fetch_online_html(detail_url), display_name)
        except Exception:
            continue
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
                "evidence": evidence,
                "parser": "custom_qinghai_ecology_ldhd_online_v1",
                "selector_summary": ".scroll_main姓名链接；ldhd姓名到领导简介前职务",
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
