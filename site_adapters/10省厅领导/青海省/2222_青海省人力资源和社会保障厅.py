from __future__ import annotations

import sys
import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2222',
 'domain': 'rst.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'qinghai_hrss_iframe_leaders_v1',
 'leader_region_selector': '#gkframe:/zfxxgk/gkzzjgldjj/index.html',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '主页面通过iframe加载领导简介',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.rsb_con:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导简介位于gkframe iframe，在线读取姓名职务'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def _fetch_online_html(url: str) -> str:
    """在线读取官方 iframe 页面。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在线解析青海省人社厅 iframe 领导列表。"""
    main_soup = BeautifulSoup(html, "html.parser")
    iframe = main_soup.select_one('iframe#gkframe[src*="gkzzjgldjj/index.html"]')
    if iframe is not None:
        iframe_path = str(iframe.get("src") or "")
    else:
        path_match = re.search(r"[\"'](?P<src>/zfxxgk/gkzzjgldjj/index\.html)[\"']", html)
        iframe_path = path_match.group("src") if path_match else ""
    if not iframe_path:
        return []
    iframe_url = urljoin(page_rule["url"], iframe_path)
    iframe_soup = BeautifulSoup(_fetch_online_html(iframe_url), "html.parser")
    records: list[object] = []
    for link in iframe_soup.select(".con-rt.rt.lead ul.ulf li a[href]"):
        text_node = link.select_one("span.sp1")
        text = re.sub(r"，+", "，", re.sub(r"[\s\u3000\xa0]+", "", text_node.get_text("，", strip=True) if text_node else ""))
        match = re.fullmatch(r"(?P<duty>.+?)[：:]，?(?P<name>[\u3400-\u9fff·]{2,6})", text)
        if not match:
            continue
        detail_url = urljoin(iframe_url, str(link.get("href") or ""))
        records.append(_make_record(page_rule, match.group("name"), match.group("duty"), detail_url))
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
