from __future__ import annotations

import sys
import re
from urllib.parse import urljoin
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3268',
 'domain': 'www.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_yunnan_gov_leader_v1',
 'leader_region_selector': '.zfld_content .nld',
 'name_selector': '.zfld_content .nld a span',
 'duty_selector': '.zfld_content .nld a b',
 'detail_link_selector': '.zfld_content .nld a[href]',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析云南省政府领导卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".zfld_content .nld"):
        link = card.select_one("a[href]:has(span)")
        name_node = card.select_one("a span")
        duty_node = card.select_one("a b")
        if not link or not name_node or not duty_node:
            continue
        name = re.sub(r"[\s\u00a0]+", "", name_node.get_text("", strip=True))
        evidence = re.sub(r"[\s\u00a0]+", " ", duty_node.get_text(" ", strip=True)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not evidence:
            continue
        if name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, link.get("href", ""))
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": ".zfld_content .nld b/span",
            }
        )
    return rows


if __name__ == "__main__":
    main()
