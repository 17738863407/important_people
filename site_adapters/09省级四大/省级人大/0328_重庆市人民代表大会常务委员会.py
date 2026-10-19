from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0328',
 'domain': 'www.cqrd.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_cqrd_leaderlist_v1',
 'leader_region_selector': '.leaderlist tr',
 'name_selector': '.leaderlist td.text-end a',
 'duty_selector': '.leaderlist td.title',
 'detail_link_selector': '.leaderlist td.text-end a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leaderlist tr',
                     'name_selector': '.leaderlist td.text-end a',
                     'duty_selector': '.leaderlist td.title',
                     'detail_link_selector': '.leaderlist td.text-end a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线DOM直接解析常委会领导表格'},
             'migration': {'source': 'live_official_leader_table',
                           'verified_status': 'online',
                           'behavior_changed': True}}}


def parse_page(html, final_url, page_rule):
    """解析重庆市人大常委会领导之窗表格。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    parser = str(page_rule.get("parser", ""))
    rows = []

    for row in soup.select(".leaderlist tr"):
        duty_node = row.select_one("td.title")
        if duty_node is None:
            continue
        duty = re.sub(r"[\s\u3000\xa0]+", "", duty_node.get_text(" ", strip=True))
        if not duty:
            continue
        for link in row.select("td.text-end a[href]"):
            name = re.sub(r"[\s\u3000\xa0]+", "", link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                continue
            detail_url = urljoin(final_url, link.get("href") or "")
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "parser": parser,
                    "selector_summary": ".leaderlist常委会领导表格",
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
