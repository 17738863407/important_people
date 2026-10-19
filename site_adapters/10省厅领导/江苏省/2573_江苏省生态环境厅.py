from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2573',
 'domain': 'sthjt.jiangsu.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_jiangsu_ecology_online_detail_v1',
 'leader_region_selector': '.main',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
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
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '厅领导列表和详情页均为静态 HTML'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _extract_duty(detail_html: str, display_name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    main = soup.select_one(".main") or soup.body or soup
    text = _clean_text(main.get_text(" ", strip=True))
    before_intro = text.split(" 简介 ", 1)[0]
    duty = ""
    for candidate in (display_name, display_name.replace("·", "•")):
        pos = before_intro.rfind(candidate)
        if pos >= 0:
            duty = _clean_text(before_intro[pos + len(candidate):])
            break
    if not duty:
        match = re.search(r"(?P<duty>省生态环境厅[^简]{2,120})\s+简介", text)
        if match:
            duty = _clean_text(match.group("duty"))
    duty = re.sub(r"[（(]挂职[）)]", "", duty)
    return re.sub(r"\s*([，、])\s*", r"\1", duty).strip("，、 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".main") or soup
    rows: list[dict] = []
    seen: set[str] = set()
    for link in main.find_all("a", href=True)[:15]:
        display_name = _clean_text(link.get_text(" ", strip=True))
        name = _compact_name(display_name)
        if not name or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="requests", timeout=20)
        except Exception:
            continue
        duty = _extract_duty(detail_result.html, display_name)
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
                "selector_summary": ".main厅领导前15链接；详情姓名到简介前职务",
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
