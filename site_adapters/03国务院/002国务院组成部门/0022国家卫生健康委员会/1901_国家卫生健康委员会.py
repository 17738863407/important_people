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

PAGE_RULE = {'rule_id': '1901',
 'domain': 'www.nhc.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'chrome_cdp',
 'extract_mode': 'custom',
 'collector': 'chrome_cdp',
 'parser': 'online_nhc_leader_links_v1',
 'leader_region_selector': '.w1140.bgfff a[href*="/wjw/wld/"]',
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
 'locator': {'css': {'leader_region_selector': '.w1140.bgfff a[href*="/wjw/wld/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线主页含姓名链接，在线Chrome详情页含职务'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select('.w1140.bgfff a[href*="/wjw/wld/"]'):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome_cdp", timeout=45)
        except Exception:
            continue
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        detail_name_node = detail_soup.select_one(".ldxx_con .ldxx_con_tit")
        duty_node = detail_soup.select_one(".ldxx_con .ldxx_con_subtit")
        detail_name = clean_text(detail_name_node.get_text(" ", strip=True)).replace(" ", "") if detail_name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if detail_name != name or not duty:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_result.final_url,
            "evidence": duty,
            "selector_summary": "委领导主页姓名链接+在线Chrome详情.ldxx_con_tit/ldxx_con_subtit",
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
