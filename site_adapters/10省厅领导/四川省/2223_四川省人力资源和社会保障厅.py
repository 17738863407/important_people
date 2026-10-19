from __future__ import annotations

import html as html_lib
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2223',
 'domain': 'rst.sc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'sichuan_hrss_leader_intro_links_v1',
 'leader_region_selector': '.jgszxxgk dd a',
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
             'api': {'enabled': False, 'reason': '领导简介列表给出姓名链接，职务由详情页现任句确认后映射'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return _clean_text(raw.decode(encoding, errors="ignore"))


def _clean_evidence(value: str) -> str:
    """只保留当前现任段的职务部分，排除明确分工文本。"""
    value = re.sub(r"^现任\s*", "", value)
    value = re.split(r"\s+分工\s*", value, maxsplit=1)[0]
    value = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", value)
    return value.strip(" 。，、；")


def _make_record(page_rule: dict, name: str, duty: str, evidence: str, detail_url: str) -> object:
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析四川省人社厅领导简介列表，并补入详情页确认职务。"""
    section_match = re.search(r'(?is)<div class="gknr_list jgszxxgk">.*?</div>', html)
    source = section_match.group(0) if section_match else html
    records: list[object] = []
    seen: set[str] = set()
    for _quote, href, inner_html in re.findall(r'''(?is)<a\b[^>]*href=(['"])(.*?)\1[^>]*>(.*?)</a>''', source):
        name = _clean_text(inner_html)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, href)
        try:
            detail_text = _fetch_text(detail_url)
        except Exception:
            continue
        current = re.search(r"现任[^。]*。", detail_text)
        if current:
            duty = _clean_evidence(current.group(0))
            seen.add(name)
            records.append(_make_record(page_rule, name, duty, duty, detail_url))
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
