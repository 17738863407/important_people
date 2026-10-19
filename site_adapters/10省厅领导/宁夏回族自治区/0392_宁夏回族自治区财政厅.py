from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0392',
 'domain': 'czt.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_ningxia_finance_leader_list_v1',
 'leader_region_selector': '.gl-list li',
 'name_selector': '.gl-list li a 文本末尾姓名',
 'duty_selector': '.gl-list li a 文本姓名前',
 'detail_link_selector': '.gl-list li a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.gl-list'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.gl-list li a[href]',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '.gl-list',
                     'max_detail_links': 50},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css+regex',
 'locator': {'css': {'leader_region_selector': '.gl-list li',
                     'name_selector': '.gl-list li a 文本末尾姓名',
                     'duty_selector': '.gl-list li a 文本姓名前',
                     'detail_link_selector': '.gl-list li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.gl-list'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线列表直出职务和姓名'}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\u2003', ' ').replace('\u2002', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def split_duty_name(value: str) -> tuple[str, str] | None:
    text = clean_text(value)
    match = re.match(r'(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fa5](?:\s*[\u4e00-\u9fa5]){1,3})$', text)
    if not match:
        return None
    name = re.sub(r'\s+', '', match.group('name'))
    duty = clean_text(match.group('duty'))
    if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.gl-list li'):
        link = item.select_one('a[href]')
        if not link:
            continue
        parsed = split_duty_name(link.get_text(' ', strip=True))
        if not parsed:
            continue
        name, duty = parsed
        page_url = str(page_rule.get('url', '')) or final_url
        detail_url = urljoin(page_url, link.get('href', ''))
        detail = urlparse(detail_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {'http', 'https'}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip('/') == source.path.rstrip('/')
            or not detail.path.lower().endswith(('.html', '.htm'))
        ):
            detail_url = ''
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'organization': page_rule['organization'],
            'url': page_rule['url'],
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_ningxia_finance_leader_list_v1',
            'selector_summary': 'leader=.gl-list li；name=a 文本末尾姓名；duty=a 文本姓名前；detail=a[href]；api_enabled=False',
        })
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.models import PersonRecord
    from crawler_core.runner import safe_filename

    page_rule = apply_business_source(PAGE_RULE)
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        str(page_rule["url"]),
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    raw_rows = parse_page(response.text, response.url, page_rule)
    records = [
        PersonRecord(
            organization=str(row.get("organization", "")),
            url=str(row.get("url", "")),
            name=str(row.get("name", "")),
            duty=str(row.get("duty", "")),
            detail_url=str(row.get("detail_url", "")),
            evidence=str(row.get("evidence", "")),
            confidence=str(row.get("confidence", "high")),
            parser=str(row.get("parser", "")),
            selector_summary=str(row.get("selector_summary", "")),
            script_sequence=str(page_rule["rule_id"]),
        )
        for row in raw_rows
    ]
    if not records:
        raise RuntimeError("在线直连获取成功，但原定位解析结果为空")
    output_name = (
        f"{page_rule['rule_id']}_{safe_filename(page_rule['page_type'])}_"
        f"{safe_filename(page_rule['load_mode'])}_{safe_filename(page_rule['organization'])}.txt"
    )
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, records)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
