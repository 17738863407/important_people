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

PAGE_RULE = {'rule_id': '0983',
 'domain': 'www.hljrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hljrd_leader_window_v2',
 'leader_region_selector': '.lingdao_info_rights > ul > li',
 'name_selector': ':scope > div > a[href^="/content_leader.html?id="]',
 'duty_selector': ':scope > span',
 'detail_link_selector': ':scope > div > a[href^="/content_leader.html?id="]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '领导之窗按职务分组展示人物；必须从当前 li 的 span 动态读取职务，禁止按姓名推定',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.lingdao_info_rights > ul > li',
                     'name_selector': ':scope > div > a[href^="/content_leader.html?id="]',
                     'duty_selector': ':scope > span',
                     'detail_link_selector': ':scope > div > a[href^="/content_leader.html?id="]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩人大站领导姓名中的空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按网页职务分组解析黑龙江省人大常委会领导之窗。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "group=.lingdao_info_rights>ul>li；"
        "duty=:scope>span；"
        "name_link=:scope>div>a[href^=/content_leader.html?id=]"
    )

    for group in soup.select(".lingdao_info_rights > ul > li"):
        duty_node = group.select_one(":scope > span")
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue

        for link in group.select(':scope > div > a[href^="/content_leader.html?id="]'):
            name = clean_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            detail_url = urljoin(page_url, link.get("href", ""))
            rows.append(
                {
                    "organization": organization,
                    "url": page_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": "" if detail_url == page_url else detail_url,
                    "evidence": duty,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": selector_summary,
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
