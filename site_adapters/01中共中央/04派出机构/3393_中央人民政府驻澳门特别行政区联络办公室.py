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

PAGE_RULE = {'rule_id': '3393',
 'domain': 'www.zlb.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'MacaoLiaisonOfficeLeaderCardParser_v1',
 'leader_region_selector': '.con-right01 dl dt, .con-right01 dl dd li',
 'name_selector': 'h3',
 'duty_selector': 'p',
 'detail_link_selector': 'h3 parent a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.con-right01 dl dt, .con-right01 dl dd li',
                     'name_selector': 'h3',
                     'duty_selector': 'p',
                     'detail_link_selector': 'h3 parent a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析澳门中联办办领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for item in soup.select(".con-right01 dl dt, .con-right01 dl dd li"):
        name_node = item.select_one("h3")
        duty_node = item.select_one("p")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not name or not duty:
            continue
        link = name_node.find_parent("a", href=True) or item.select_one("a[href]")
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link.get("href", "") if link else ""),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.con-right01 dl dt/dd li；name=h3；duty=p；detail=h3父级a[href]",
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
