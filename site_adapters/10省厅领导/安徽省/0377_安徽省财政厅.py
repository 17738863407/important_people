from __future__ import annotations

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

PAGE_RULE = {'rule_id': '0377',
 'domain': 'czt.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'raw_http',
 'parser': 'page_list_anhui_finance_detail_label_v1',
 'leader_region_selector': '.xxgk_nav_list li',
 'name_selector': 'a[href]',
 'duty_selector': '详情页“职务职级”字段',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': ['.xxgk_nav_list'], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'detail_label_duty_rank_before_division_v1',
                     'detail_name_selector': '列表姓名',
                     'detail_duty_selector': '职务职级 至 分工',
                     'detail_content_selector': 'body',
                     'max_detail_links': 50},
 'risk_flag': '入口查询参数包含catId，必须保留原始HTTP响应，禁止跟随脚本跳转丢失目标栏目',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css+detail',
 'locator': {'css': {'leader_region_selector': '.xxgk_nav_list li',
                     'name_selector': 'a[href]',
                     'duty_selector': '详情页“职务职级”字段',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.xxgk_nav_list'],
                                       'exclude_selectors': []}}},
 'api': {'enabled': False, 'reason': '列表页仅姓名日期，职务在静态详情页中'},
}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def normalize_duty(value: str, organization: str) -> str:
    duty = clean_text(value).rstrip('。')
    duty = re.sub(rf'^{re.escape(organization)}', '', duty)
    return clean_text(duty).strip('，、；;')


def fetch_detail_duty(url: str, organization: str) -> tuple[str, str]:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    text = clean_text(BeautifulSoup(response.text, 'lxml').get_text(' ', strip=True))
    match = re.search(
        r'职务职级[:：]\s*(?P<duty>.+?)\s*(?:分工[:：]|免责声明|网站地图|版权所有)',
        text,
    )
    if not match:
        return '', text
    evidence = clean_text(match.group('duty'))
    return normalize_duty(evidence, organization), evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.xxgk_nav_list li'):
        link = item.select_one('a[href]')
        if not link:
            continue
        name = clean_text(link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        href = str(link.get('href', '')).strip()
        if not href or href.lower().startswith(('#', 'javascript:')):
            continue
        detail_url = urljoin(final_url or page_rule['url'], href)
        if detail_url.rstrip('/') == (final_url or page_rule['url']).rstrip('/'):
            continue
        duty, evidence_text = fetch_detail_duty(detail_url, page_rule['organization'])
        if not duty:
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': evidence_text,
            'confidence': 'high',
            'parser': 'page_list_anhui_finance_detail_label_v1',
            'selector_summary': 'leader=.xxgk_nav_list li；name=a[href]；duty=detail 职务职级字段；detail=a[href]；api_enabled=False',
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
