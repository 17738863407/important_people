from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2214',
 'domain': 'rst.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'guizhou_hrss_leader_cards_v1',
 'leader_region_selector': '.zfxxgk_zdgkc dd a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '政府领导卡片给出姓名链接，职务由详情页现任句确认后映射'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str, evidence: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=evidence,
        confidence="high",
        parser=page_rule["parser"],
    )


def _fetch_detail_html(detail_url: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def _extract_detail(detail_html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".ldxx_right .zw_name .name")
    duty_node = soup.select_one(".ldxx_right .zw_name .zw")
    name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else fallback_name
    duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
    meta = soup.find("meta", attrs={"name": "Description"})
    description = _clean_text(meta.get("content", "")) if meta else ""
    sentence = re.search(r"现任[^。]*。", description)
    evidence = sentence.group(0).removeprefix("现任").removesuffix("。") if sentence else duty
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析贵州省人社厅政府领导卡片，并补入详情页确认职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    links = soup.select(".zfxxgk_zdgkc dd a[href][title]")
    if len(links) < 2:
        response = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.select(".zfxxgk_zdgkc dd a[href][title]")
    records: list[object] = []
    seen: set[str] = set()
    for link in links:
        list_name = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        detail_url = urljoin(source_url, link.get("href", ""))
        try:
            name, duty, evidence = _extract_detail(_fetch_detail_html(detail_url), list_name)
        except Exception:
            continue
        if name and duty and name not in seen:
            seen.add(name)
            records.append(_make_record(page_rule, name, duty, detail_url, evidence))
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
