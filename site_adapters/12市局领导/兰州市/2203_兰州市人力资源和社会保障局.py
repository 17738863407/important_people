from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2203',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'custom_lanzhou_rsj_list_detail_v2',
 'leader_region_selector': 'script[type="text/xml"] record',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href*="art_10645_"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'raw_http',
                     'detail_link_selector': 'a[href*="art_10645_"]',
                     'detail_name_selector': '#zoom p:first-of-type',
                     'detail_duty_selector': '#zoom p',
                     'detail_content_selector': '#zoom',
                     'max_detail_links': 50},
 'risk_flag': '目录链接位于 text/xml 脚本数据；详情首段为简历、下一段为现职，后续段落为职责和分工',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
             'locator': {'css': {'leader_region_selector': 'script[type="text/xml"] record',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href*="art_10645_"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前目录 text/xml 数据和详情 HTML 均在线直出'},
             'migration': {'source': 'current_online_list_and_detail',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2000-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([，、；：])\s*", r"\1", value)


def extract_duty(detail_html: str, name: str) -> str:
    """从当前人物详情正文中提取简历后的独立现职段落。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("#zoom")
    if content is None:
        return ""
    paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in content.select("p")]
    paragraphs = [p for p in paragraphs if p]
    biography_index = next((index for index, text in enumerate(paragraphs) if text.startswith(name + "，")), -1)
    if biography_index < 0 or biography_index + 1 >= len(paragraphs):
        return ""
    duty = re.sub(r"^现任", "", paragraphs[biography_index + 1]).rstrip("。；; ")
    if not re.search(r"书记|局长|副局长|组长|调研员|监察官", duty):
        return ""
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_by_raw_requests

    rows: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'href="(?P<href>[^"]*art_10645_[^"]+\.html)"\s+title="(?P<name>[^"]+)"'
    )
    for match in pattern.finditer(html):
        name = clean_text(match.group("name")).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        if name in seen:
            continue
        detail_url = urljoin(final_url or page_rule["url"], match.group("href"))
        try:
            result = fetch_by_raw_requests(detail_url)
            detail_url = result.final_url
            duty = extract_duty(result.html, name)
        except Exception:
            continue
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "list=text/xml record order; detail=#zoom; duty=paragraph after biography",
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
