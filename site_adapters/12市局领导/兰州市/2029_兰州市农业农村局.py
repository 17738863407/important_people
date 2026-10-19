from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2029',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'custom_lanzhou_nync_list_detail_v2',
 'leader_region_selector': 'script[type="text/xml"] record',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href*="art_2170_"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'raw_http',
                     'detail_link_selector': 'a[href*="art_2170_"]',
                     'detail_name_selector': '#zoom strong',
                     'detail_duty_selector': '#zoom',
                     'detail_content_selector': '#zoom',
                     'max_detail_links': 50},
 'risk_flag': '目录人物链接位于 text/xml 脚本数据中，详情页正文含职责和分工，职务须在职责标记前截断',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'script[type="text/xml"] record',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href*="art_2170_"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录 text/xml 数据和详情 HTML 均为当前在线页面直出'},
             'migration': {'source': 'current_online_list_and_detail',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2000-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([，、；：])\s*", r"\1", value)


def extract_duty_from_detail(name: str, detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("#zoom")
    if content is None:
        return ""
    text = clean_text(content.get_text(" ", strip=True))
    if name not in text:
        return ""
    text = text.split(name, 1)[1]
    for marker in ["，负责", "，主持", "。", "分管"]:
        if marker in text:
            text = text.split(marker, 1)[0]
            break
    return clean_text(text.strip(" ，。；;:："))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_by_raw_requests

    rows = []
    seen_names = set()
    pattern = re.compile(
        r'href="(?P<href>[^"]*art_2170_[^"]+\.html)"\s+title="(?P<name>[^"]+)"'
    )
    for match in pattern.finditer(html):
        name = clean_text(match.group("name")).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url or page_rule["url"], match.group("href"))
        try:
            result = fetch_by_raw_requests(detail_url)
            detail_url = result.final_url
            duty = extract_duty_from_detail(name, result.html)
        except Exception:
            continue
        if not duty:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "selector_summary": "list=text/xml record order; detail=#zoom; duty before responsibility marker",
        })
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
