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

PAGE_RULE = {'rule_id': '2401',
 'domain': 'www.shanxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': '',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按山西省政府首页省长卡片及领导职务分组动态解析。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def append_row(link, evidence: str, name_text: str = "") -> None:
        name = "".join((name_text or link.get_text(" ", strip=True)).split())
        href = str(link.get("href", "")).strip()
        if not name or not evidence or name in seen or not href or href.startswith(("#", "javascript:")):
            return
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": urljoin(final_url or source_url, href)})

    title = soup.select_one("p.gov-leader-title")
    if title:
        title_link = title.select_one(page_rule["detail_link_selector"])
        duty_node = title.select_one("span")
        evidence = " ".join(duty_node.get_text(" ", strip=True).split()).rstrip("：:") if duty_node else ""
        description = title.find_next_sibling("p", class_="gov-leader-desc")
        description_text = " ".join(description.get_text(" ", strip=True).split()) if description else ""
        current_match = re.search(r"现任[^。]*。", description_text)
        if current_match:
            evidence = clean_current_evidence(current_match.group(0))
        if title_link:
            append_row(title_link, evidence)

    for group in soup.select("dl.gov-leader-col"):
        duty_node = group.select_one("dt")
        evidence = " ".join(duty_node.get_text(" ", strip=True).split()).rstrip("：:") if duty_node else ""
        for link in group.select("dd a[href]"):
            name_node = link.select_one("em")
            if name_node:
                append_row(link, evidence, name_node.get_text(" ", strip=True))
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
