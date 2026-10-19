from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1283',
 'domain': 'www.jxrd.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_jiangxi_rd_leader_group_cards_v1',
 'leader_region_selector': '.leader-head',
 'name_selector': '.leader-list a.name',
 'duty_selector': '.leader-head h1',
 'detail_link_selector': '.leader-list a.name[href]',
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
 'risk_flag': '旧规则使用脆弱长路径且字段选择器为空，页面包含领导活动导航和重复左侧名单，容易漏人或混入导航；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader-head',
                     'name_selector': '.leader-list a.name',
                     'duty_selector': '.leader-head h1',
                     'detail_link_selector': '.leader-list a.name[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    return re.sub(r"\s+", "", duty)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江西省人大常委会主任会议成员分组名单。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=.leader-head；field=h1 + .leader-list a.name"
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for group in soup.select(".leader-head"):
        duty_node = group.select_one("h1")
        duty = clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in group.select(".leader-list a.name[href]"):
            name = clean_name(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "organization": organization,
                    "url": page_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(page_url, link.get("href", "")),
                    "evidence": duty,
                    "parser": parser,
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
