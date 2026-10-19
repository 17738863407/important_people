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

PAGE_RULE = {'rule_id': '1851',
 'domain': 'www.ndcpa.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'online_ndcpa_leader_links_v1',
 'leader_region_selector': '.row.lscy a[href*="common/list.html"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'none',
                     'raw': '{"required":true,"mode":"person_name_link","candidate_links":[],"discovered_at":"20260716_084944"}'},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.row.lscy a[href*="common/list.html"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线主页含成员链接，人物详情页含职务'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select('.row.lscy a[href*="common/list.html"]'):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        try:
            response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
        except requests.RequestException:
            continue
        detail_soup = BeautifulSoup(response.text, "html.parser")
        detail_name_node = detail_soup.select_one(".lddetailright h1")
        duty_node = detail_soup.select_one(".lddetailright p")
        detail_name = clean_text(detail_name_node.get_text(" ", strip=True)).replace(" ", "") if detail_name_node else ""
        duty = clean_text(duty_node.get_text("；", strip=True)) if duty_node else ""
        if detail_name != name or not duty:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "selector_summary": "主页成员链接+在线详情.lddetailright h1/p",
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
