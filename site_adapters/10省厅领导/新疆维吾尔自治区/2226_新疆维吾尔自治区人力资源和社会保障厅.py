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

PAGE_RULE = {'rule_id': '2226',
 'domain': 'rst.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang_hrss_c112670_leader_links_v1',
 'leader_region_selector': 'a[href*="/c112670/"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a[href*="/c112670/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified_online', 'behavior_changed': True}}}


def _split_name_duty(text: str) -> tuple[str, str]:
    markers = ["厅党组", "驻厅", "社会保险中心", "公共就业服务中心", "二级巡视员"]
    positions = [text.find(marker) for marker in markers if text.find(marker) > 0]
    if not positions:
        return "", ""
    duty_start = min(positions)
    name = "".join(text[:duty_start].split())
    duty = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作|主持工作)\s*[）)]", "", text[duty_start:]).strip()
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区人力资源和社会保障厅领导之窗链接列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.select('a[href*="/c112670/"]'):
        text = " ".join(link.get_text(" ", strip=True).split())
        name, duty = _split_name_duty(text)
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "evidence": duty,
            }
        )
    return records


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
