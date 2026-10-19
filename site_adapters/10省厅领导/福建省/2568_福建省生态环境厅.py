from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2568',
 'domain': 'sthjt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_fujian_ecology_leader_menu_v1',
 'leader_region_selector': '.leader_name_list',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
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
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.warp.page_bg:nth-of-type(1) > '
                                               'div.main:nth-of-type(3) > div.content > div.row.pad_t_base > '
                                               'div.content_bg_02.pad_base > div.trt-row.trt-row-large:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '省厅领导详情页侧栏静态列出完整领导姓名和职务'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one(".leader_name_list")
    if not box:
        return []
    rows: list[dict] = []
    seen: set[str] = set()
    for link in box.select("ul.dropdown_menu a[href]"):
        spans = [_clean_text(span.get_text(" ", strip=True)) for span in link.find_all("span")]
        if len(spans) >= 2:
            raw_name = spans[0]
            duty = _clean_text(" ".join(spans[1:]))
        else:
            text = _clean_text(link.get_text(" ", strip=True))
            match = re.match(r"(?P<name>[\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s+(?P<duty>.+)", text)
            if not match:
                continue
            raw_name = match.group("name")
            duty = _clean_text(match.group("duty"))
        name = _clean_name(raw_name)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(page_rule["url"], link.get("href") or "")
        if detail_url.rstrip("/") == page_rule["url"].rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_fujian_ecology_leader_menu_v1",
                "selector_summary": ".leader_name_list下拉领导项",
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
