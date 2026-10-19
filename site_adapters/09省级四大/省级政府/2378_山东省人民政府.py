from __future__ import annotations

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

PAGE_RULE = {'rule_id': '2378',
 'domain': 'www.shandong.gov.cn',
 'page_type': '人物列表完整页',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'shandong_government_leader_group_parser_v1',
 'source_parser': 'shandong_government_leader_group_parser_v1',
 'leader_region_selector': 'body',
 'name_selector': '.wip_ldconryli a[href]',
 'duty_selector': '.wip_ldconzw',
 'detail_link_selector': '.wip_ldconryli a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按山东省政府领导职务分组解析人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in soup.select(".wip_ldcon"):
        duty_node = group.select_one(page_rule["duty_selector"])
        evidence = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if not evidence:
            continue
        for link in group.select(page_rule["name_selector"]):
            name = "".join(link.get_text(" ", strip=True).split())
            if not name or name in seen:
                continue
            seen.add(name)
            href = str(link.get("href", "")).strip()
            detail_url = urljoin(final_url or page_rule["url"], href) if href and not href.startswith(("#", "javascript:")) else ""
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url})
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
