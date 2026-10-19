from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2297',
 'page_type': '人物列表完整页',
 'structure_group': 'tianjin_justice_leader_intro_cards',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_tianjin_justice_intro_v2',
 'leader_region_selector': '.leaders > .leader',
 'name_selector': '.leader-desc .ldlbxq首句职务后姓名',
 'duty_selector': '.leader-desc .ldlbxq首句姓名前原文',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '领导信息',
                   'end_anchor': '',
                   'include_selectors': ['.leaders'],
                   'exclude_selectors': ['.header', '.footer']},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'risk_flag': '人物姓名与职务连续书写；只在人物卡片首句内按末尾职务边界拆分，不读取后续分管职责',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leaders > .leader',
                     'name_selector': '.leader-desc .ldlbxq首句职务后姓名',
                     'duty_selector': '.leader-desc .ldlbxq首句姓名前原文',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '领导信息',
                                       'end_anchor': '',
                                       'include_selectors': ['.leaders'],
                                       'exclude_selectors': ['.header', '.footer']}},
             'api': {'enabled': False, 'reason': '在线HTML人物卡片已直接给出姓名、职务和简介'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白，不改写业务原文。"""
    return re.sub(r'\s+', ' ', (value or '').replace('\u3000', ' ').replace('\xa0', ' ')).strip()


def split_intro(intro: str) -> tuple[str, str, str]:
    """从当前人物简介首句拆出姓名、原始职务和可回指证据。"""
    text = clean_text(intro)
    head_match = re.match(r'^(?P<head>.+?)[，,](?:男|女)[，,]', text)
    if not head_match:
        return '', '', ''
    evidence = clean_text(head_match.group('head'))
    person_match = re.match(
        r'^(?P<duty>.+(?:书记|局长|组长|主任|巡视员|监察官|总工程师|总法律顾问))'
        r'(?P<name>[\u4e00-\u9fa5·]{2,4})$',
        evidence,
    )
    if not person_match:
        return '', '', ''
    return person_match.group('name'), person_match.group('duty'), evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析天津市司法局领导信息段落。"""
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    for node in soup.select('.leaders > .leader .leader-desc .ldlbxq'):
        name, duty, evidence = split_intro(node.get_text(' ', strip=True))
        if not name or not duty:
            continue
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_tianjin_justice_intro_v2',
        })
    if not rows:
        raise RuntimeError('领导信息人物卡片未解析到有效姓名和职务')
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
