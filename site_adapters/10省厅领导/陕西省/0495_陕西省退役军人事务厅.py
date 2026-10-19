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

PAGE_RULE = {
    'rule_id': '0495',
    'domain': 'dva.shaanxi.gov.cn',
    'page_type': '多人物详情合并页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'page_inline',
    'collector': 'static_http',
    'parser': 'page_inline_shaanxi_dva_swiper_leader_v1',
    'leader_region_selector': '.ldxx .swiper-slide',
    'name_selector': '.ldxx .swiper-slide h2',
    'duty_selector': '.ldxx .swiper-slide a p',
    'detail_link_selector': '.ldxx .swiper-slide a[href]',
    'content_scope': {
        'start_anchor': '领导信息',
        'end_anchor': '内设机构',
        'include_selectors': ['.ldxx .swiper-wrapper'],
        'exclude_selectors': ['.jgsz', '.footer'],
    },
    'detail_strategy': {
        'required': False,
        'mode': 'none',
        'candidate_links': [],
    },
    'risk_flag': '页面同时含内设机构和直属单位；必须限定.ldxx轮播卡片',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '.ldxx .swiper-slide',
            'name_selector': '.ldxx .swiper-slide h2',
            'duty_selector': '.ldxx .swiper-slide a p',
            'detail_link_selector': '.ldxx .swiper-slide a[href]',
            'content_scope': {
                'start_anchor': '领导信息',
                'end_anchor': '内设机构',
                'include_selectors': ['.ldxx .swiper-wrapper'],
                'exclude_selectors': ['.jgsz', '.footer'],
            },
        },
        'api': {'enabled': False, 'reason': '领导卡片由页面 DOM 直接提供'},
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.ldxx .swiper-slide'):
        link = item.select_one('a[href]')
        name_node = item.select_one('h2')
        duty_node = item.select_one('a p')
        if not link or not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True)).strip('。')
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        evidence_node = item.select_one('.lddetail')
        evidence_text = clean_text(evidence_node.get_text(' ', strip=True)) if evidence_node else ''
        evidence_match = re.search(r'现任[^。]*。', evidence_text)
        evidence = re.sub(r'^现任\s*', '', evidence_match.group(0)).removesuffix('。').strip() if evidence_match else duty
        rows.append({
            'name': name,
            'duty': '',
            'detail_url': detail_url,
            'evidence': evidence,
            'confidence': 'high',
            'parser': 'page_inline_shaanxi_dva_swiper_leader_v1',
            'selector_summary': 'leader=.ldxx .swiper-slide；name=h2；duty=a p；detail=a[href]；api_enabled=False',
            'order': str(len(rows) + 1),
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
