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

PAGE_RULE = {
    'rule_id': '0465',
    'domain': 'dnr.sc.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_to_detail',
    'collector': 'static_http',
    'parser': 'page_list_sichuan_dnr_resume_current_duty_v1',
    'leader_region_selector': '.item dl:first-of-type .lingdao-box:first-of-type a[href]',
    'name_selector': '.item dl:first-of-type .lingdao-box:first-of-type a .title',
    'duty_selector': '详情页 .content-new .rowed 简历段“现任...”',
    'detail_link_selector': '.item dl:first-of-type .lingdao-box:first-of-type a[href]',
    'content_scope': {
        'start_anchor': '领导简介',
        'end_anchor': '机构职能',
        'include_selectors': ['.item dl:first-of-type .lingdao-box:first-of-type'],
        'exclude_selectors': ['.lingdao-box1', '.lingdao-box2'],
    },
    'detail_strategy': {
        'required': True,
        'mode': 'list_to_detail',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '.item dl:first-of-type .lingdao-box:first-of-type a[href]',
        'detail_parser': 'detail_sichuan_dnr_resume_current_sentence_v1',
        'detail_name_selector': '列表姓名',
        'detail_duty_selector': '.content-new .rowed 简历段',
        'detail_content_selector': '.content-new',
        'max_detail_links': 50,
        'candidate_links': [],
    },
    'risk_flag': '第二轮定向修复',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css+detail',
    'locator': {
        'css': {
            'leader_region_selector': '.item dl:first-of-type .lingdao-box:first-of-type a[href]',
            'name_selector': '.item dl:first-of-type .lingdao-box:first-of-type a .title',
            'duty_selector': '详情页 .content-new .rowed 简历段“现任...”',
            'detail_link_selector': '.item dl:first-of-type .lingdao-box:first-of-type a[href]',
            'content_scope': {
                'start_anchor': '领导简介',
                'end_anchor': '机构职能',
                'include_selectors': ['.item dl:first-of-type .lingdao-box:first-of-type'],
                'exclude_selectors': ['.lingdao-box1', '.lingdao-box2'],
            },
        },
        'api': {'enabled': False, 'reason': '列表页和详情页均为静态 HTML'},
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def split_sentences(text: str) -> list[str]:
    return [clean_text(part) for part in re.split(r'[。；;]', text) if clean_text(part)]


def clean_evidence(value: str) -> str:
    """删除独立状态标记，保留具体职务和职级。"""
    text = re.sub(r'[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]', '', value)
    text = re.sub(r'\s*([、，,；;])\s*', r'\1', text)
    return text.strip('，,、；;。 ')


def extract_duty_from_resume(resume: str) -> str:
    match = re.search(r'现任(?P<duty>[^。；;]+)', resume)
    if match:
        return clean_evidence(clean_text(match.group('duty')))
    for sentence in split_sentences(resume):
        if any(word in sentence for word in ['自然资源厅', '纪检监察组', '巡视员', '监察官', '总工程师', '总规划师']):
            sentence = re.sub(r'^[\u4e00-\u9fa5·]{2,8}，[^。；;]*?中共党员[，,。]?', '', sentence)
            return clean_evidence(clean_text(sentence))
    return ''


def fetch_detail_duty(url: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return ''
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, 'lxml')
    for row in soup.select('.content-new .rowed'):
        label_node = row.select_one('.tn')
        label = re.sub(r'\s+', '', label_node.get_text('', strip=True) if label_node else '')
        if '简历' not in label:
            continue
        content_node = row.select_one('.nr')
        resume = clean_text(content_node.get_text(' ', strip=True) if content_node else row.get_text(' ', strip=True))
        duty = extract_duty_from_resume(resume)
        if duty:
            return duty
    return ''


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    leader_box = soup.select_one('.item dl:first-of-type .lingdao-box:first-of-type')
    if not leader_box:
        return []
    rows = []
    seen = set()
    for link in leader_box.select('a[href]'):
        title_node = link.select_one('.title')
        name = clean_name(title_node.get_text(' ', strip=True) if title_node else link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        duty = fetch_detail_duty(detail_url)
        if not duty:
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': '',
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_list_sichuan_dnr_resume_current_duty_v1',
            'selector_summary': 'leader=.item dl:first .lingdao-box:first a[href]；name=.title；duty=detail 简历段现任句/职务句；detail=a[href]；api_enabled=False',
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
