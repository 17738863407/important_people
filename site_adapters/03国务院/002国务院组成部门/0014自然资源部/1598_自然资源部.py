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

PAGE_RULE = {'rule_id': '1598',
 'domain': 'www.mnr.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_mnr_bld_and_zghszgcs_cards_v1',
 'leader_region_selector': '#bld, .div_zghszgcs',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '#bld a[href], .div_zghszgcs a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': '#bld, .div_zghszgcs',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '#bld a[href], .div_zghszgcs a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'online_page_rule', 'verified_status': 'online_pending', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows = []
    seen = set()
    for block in soup.select("#bld, .div_zghszgcs"):
        for item in block.select("dt, dd"):
            link = item.select_one("a[href]")
            duty_node = item.select_one(".div_ldzw")
            if not link or not duty_node:
                continue
            name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            duty = clean_text(duty_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                continue
            if not re.search(r"部长|成员|组长|局长|总工程师|总规划师|总督察", duty):
                continue
            detail_url = urljoin(base_url, link.get("href", ""))
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": str(rule.get("parser", "")),
                }
            )
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
