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

PAGE_RULE = {'rule_id': '3238',
 'domain': 'yjt.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'FujianEmergencyLeaderMenuParser_v1',
 'leader_region_selector': '.leader_more + .dropdown_menu a[title]',
 'name_selector': 'span',
 'duty_selector': 'a[title] text without name',
 'detail_link_selector': '.leader_more + .dropdown_menu a[title]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader_more + .dropdown_menu a[title]',
                     'name_selector': 'span',
                     'duty_selector': 'a[title] text without name',
                     'detail_link_selector': '.leader_more + .dropdown_menu a[title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ").replace("\u2003", " ").replace("\u2002", " ")
    return " ".join(text.split())


def _clean_name(text: str) -> str:
    return _clean_text(text).replace(" ", "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析福建省应急管理厅领导下拉菜单。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(".leader_more + .dropdown_menu a[title]"):
        name_node = link.select_one("span")
        name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        title = _clean_text(link.get("title", "") or link.get_text(" ", strip=True))
        duty = _clean_text(title.replace(_clean_text(name_node.get_text(" ", strip=True)) if name_node else name, "", 1))
        if not duty:
            duty = _clean_text(link.get_text(" ", strip=True).replace(name, "", 1))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, link.get("href", ""))
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.leader_more + .dropdown_menu a[title]；name=span；duty=title去除姓名；detail=a[href]",
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
