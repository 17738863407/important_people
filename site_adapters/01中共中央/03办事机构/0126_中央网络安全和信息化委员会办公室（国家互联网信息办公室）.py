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

PAGE_RULE = {'rule_id': '0126',
 'domain': 'www.cac.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_card_cac_office_leaders_v1',
 'leader_region_selector': 'div.office-leader div.leader-content h5 + ul li',
 'name_selector': 'div.leader-name, img[alt]',
 'duty_selector': 'preceding h5',
 'detail_link_selector': 'div.office-leader a[href]',
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
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.office-leader div.leader-content h5 + ul li',
                     'name_selector': 'div.leader-name, img[alt]',
                     'duty_selector': 'preceding h5',
                     'detail_link_selector': 'div.office-leader a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '办领导卡片在静态 HTML 中按职务分组直接给出'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("div.office-leader div.leader-content")
    if not root:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div.office-leader div.leader-content h5 + ul li；"
        "name=div.leader-name, img[alt]；duty=preceding h5；detail=div.office-leader a[href]；api_enabled=False"
    )
    current_duty = ""
    for child in root.find_all(["h5", "ul"], recursive=False):
        if child.name == "h5":
            current_duty = clean_text(child.get_text(" ", strip=True))
            continue
        if child.name != "ul" or not current_duty:
            continue
        for item in child.select("li"):
            link = item.select_one("a[href]")
            name_node = item.select_one("div.leader-name")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            if not name and item.select_one("img[alt]"):
                name = clean_text(item.select_one("img[alt]").get("alt", ""))
            if not name or name in seen:
                continue
            seen.add(name)
            href = str(link.get("href", "")) if link else ""
            detail_url = urljoin(base_url, href) if href and not href.startswith(("#", "javascript:")) else ""
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            rows.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "detail_url": detail_url,
                    "evidence": current_duty,
                    "parser": str(page_rule.get("parser", "")),
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
