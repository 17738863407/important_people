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

PAGE_RULE = {'rule_id': '2165',
 'domain': 'www.qinghai.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'qinghai_gov_current_leaders_v1',
 'leader_region_selector': '.LeadershipLeftBox, .LeadershipRightBox .LeadershipItem',
 'name_selector': 'a.blue, .LeadershipItem .Title a[href]',
 'duty_selector': 'a.blue, .LeadershipItem .Title a[href]',
 'detail_link_selector': 'a.blue[href], .LeadershipItem .Title a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.LeadershipLeftBox, .LeadershipRightBox .LeadershipItem',
                     'name_selector': 'a.blue, .LeadershipItem .Title a[href]',
                     'duty_selector': 'a.blue, .LeadershipItem .Title a[href]',
                     'detail_link_selector': 'a.blue[href], .LeadershipItem .Title a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析省政府领导介绍区。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    links = soup.select(".LeadershipLeftBox a.blue[href], .LeadershipRightBox .LeadershipItem .Title a[href]")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in links:
        label = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<name>[\u4e00-\u9fff·]{2,5})", label)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "selector_summary": ".LeadershipLeftBox a.blue + .LeadershipRightBox .LeadershipItem .Title a",
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
