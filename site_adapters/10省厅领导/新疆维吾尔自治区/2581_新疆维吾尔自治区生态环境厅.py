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

PAGE_RULE = {'rule_id': '2581',
 'domain': 'sthjt.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom_parse_page',
 'collector': 'static_http',
 'parser': 'custom_xinjiang_ecology_leader_cards_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': "a[href*='ld']",
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
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href*='ld']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按同一领导卡片的姓名与职务强字段提取，避免姓名混入依据说明。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("li:has(p.leadername):has(p.leaderzw)"):
        name_node = card.select_one("p.leadername")
        duty_node = card.select_one("p.leaderzw")
        link_node = card.select_one("a[href]")
        name = "".join(name_node.get_text(" ", strip=True).split()) if name_node else ""
        duty = " ".join(duty_node.get_text(" ", strip=True).split()).rstrip("。") if duty_node else ""
        detail_url = urljoin(final_url, str(link_node.get("href") or "").strip()) if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or not detail_url or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
                     "parser": "custom_xinjiang_ecology_leader_cards_v1",
                     "selector_summary": "li同卡片p.leadername与p.leaderzw强字段；详情页不纳入当前输出"})
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
