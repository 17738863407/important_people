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

PAGE_RULE = {'rule_id': '2635',
 'domain': 'swt.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang_commerce_ldzc_cards_v1',
 'leader_region_selector': '.ldzc_box li',
 'name_selector': '.lead_name',
 'duty_selector': '.lead_level',
 'detail_link_selector': '.ldzc_box li a[href*="/c114354/"]',
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
 'locator': {'css': {'leader_region_selector': '.ldzc_box li',
                     'name_selector': '.lead_name',
                     'duty_selector': '.lead_level',
                     'detail_link_selector': '.ldzc_box li a[href*="/c114354/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'online_page', 'verified_status': 'verified', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区商务厅领导信息卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in soup.select(".ldzc_box li"):
        name_node = item.select_one(".lead_name")
        duty_node = item.select_one(".lead_level")
        link = item.select_one('a[href*="/c114354/"]')
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not name or not duty:
            continue
        detail_url = urljoin(final_url, link.get("href", "")) if link else ""
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": _clean_text(item.get_text(" ", strip=True)).removesuffix(f" {name}"),
                "source_url": final_url,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.ldzc_box li；name=.lead_name；duty=.lead_level；detail=a[href*=c114354]；api_enabled=False",
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
