from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2494',
 'domain': 'slt.jiangxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'top_leader_nav_jx_water_v1',
 'leader_region_selector': '水利厅领导导航',
 'name_selector': '领导导航链接末尾姓名',
 'duty_selector': '领导导航链接姓名前职务',
 'detail_link_selector': '水利厅领导导航a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.content:nth-of-type(2) > '
                                               'div.content_box:nth-of-type(1) > div.sltld',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线水利厅领导导航直接提供职务和姓名'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江西省水利厅顶部水利厅领导导航。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    leader_region = soup.select_one(
        "html > body > div.content:nth-of-type(2) > div.content_box:nth-of-type(1) > div.sltld"
    ) or soup.select_one("div.sltld") or soup
    page_url = str(page_rule["url"])
    organization = str(page_rule["organization"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in leader_region.select("a[href]"):
        text = " ".join(link.get_text(" ", strip=True).split())
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff]{2,4})", text)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen or not re.search(r"党组|厅长|巡视员|纪检监察", duty):
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "顶部水利厅领导导航：职务+姓名",
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
