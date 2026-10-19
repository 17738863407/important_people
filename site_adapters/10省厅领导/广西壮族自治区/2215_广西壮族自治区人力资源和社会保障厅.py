from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2215',
 'domain': 'rst.gxzf.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'guangxi_hrss_left_nav_v1',
 'leader_region_selector': '.secdnav a',
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
 'locator': {'css': {'leader_region_selector': 'html > body > div.all:nth-of-type(1) > div.content:nth-of-type(3) > '
                                               'div.wrapper > div.middle > div.mid_right:nth-of-type(3) > div.leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '左侧领导导航给出姓名链接，职务由详情页首段确认后映射'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


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


def _fetch_detail_text(detail_url: str) -> str:
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return _clean_text(raw.decode(encoding, errors="replace"))


def _extract_detail_duty(detail_text: str, name: str) -> str:
    match = re.search(rf"个人简历\s*(?P<duty>.+?){re.escape(name)}\s*[，,]", detail_text)
    return _clean_text(match.group("duty")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析广西人社厅领导之窗左侧导航，并补入详情页确认职务。"""
    nav_match = re.search(r'(?is)<div class="secdnav">.*?</div>', html)
    source = nav_match.group(0) if nav_match else html
    records: list[object] = []
    seen: set[str] = set()
    for href, title, inner_html in re.findall(r'(?is)<a\b[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*>(.*?)</a>', source):
        name = _clean_text(title or inner_html)
        detail_url = urljoin(final_url or page_rule["url"], href)
        try:
            duty = _extract_detail_duty(_fetch_detail_text(detail_url), name)
        except Exception:
            duty = ""
        if name and duty and name not in seen:
            seen.add(name)
            records.append(_make_record(page_rule, name, duty, detail_url))
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
