from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0120',
 'domain': 'bnr.jiangxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'online_jx_bnr_leader_sidebar_v1',
 'leader_region_selector': '.column_ld2 li',
 'name_selector': 'a.z3',
 'duty_selector': 'a span',
 'detail_link_selector': 'a.z3[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.column_ld2 li',
                     'name_selector': 'a.z3',
                     'duty_selector': 'a span',
                     'detail_link_selector': 'a.z3[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导专区 HTML 直接提供姓名、职务和链接'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析江西省自然资源厅领导专区左侧领导列表。"""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".column_ld2 li"):
        name_link = item.select_one("a.z3")
        duty_el = item.select_one("a span")
        name = name_link.get_text(" ", strip=True) if name_link else ""
        duty = duty_el.get_text(" ", strip=True) if duty_el else ""
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), name_link.get("href", "")) if name_link else ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        if not name or not duty:
            continue
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".column_ld2 li a.z3 + span",
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
