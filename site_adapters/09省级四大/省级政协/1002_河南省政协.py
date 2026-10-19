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

PAGE_RULE = {'rule_id': '1002',
 'domain': 'www.hnzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_cppcc_grouped_cards_v1',
 'leader_region_selector': '.wrap.write_bg.pb20',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.wrap.write_bg.pb20 a[href^="/zxld/"]',
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
 'risk_flag': '政协领导分组卡片；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.wrap.write_bg.pb20',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.wrap.write_bg.pb20 a[href^="/zxld/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def normalize_duty(value: str) -> str:
    return clean_text(value).replace("  ", "、").replace(" ", "、")


def make_row(rule: dict, base_url: str, name: str, duty: str, href: str) -> dict[str, str]:
    return {
        "organization": str(rule.get("organization", "")),
        "url": base_url,
        "name": name,
        "duty": duty,
        "detail_url": urljoin(base_url, href),
        "evidence": duty,
        "confidence": "high",
        "parser": str(rule.get("parser", "")),
    }


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    main = soup.select_one(".wrap.write_bg.pb20") or soup
    rows = []
    seen = set()

    for box in main.select(".chairman_box"):
        title_node = box.select_one(":scope > .chairman_title")
        if not title_node:
            continue
        duty = normalize_duty(title_node.get_text(" ", strip=True))
        for link in box.select(":scope > .chairman_list a[href], :scope > .vicechairman_list a[href]"):
            name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(make_row(rule, base_url, name, duty, link.get("href", "")))

    for block in main.select(".vicechairman_left"):
        title_node = block.select_one(".chairman_title")
        link = block.select_one("a[href]")
        if not title_node or not link:
            continue
        duty = normalize_duty(title_node.get_text(" ", strip=True))
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(make_row(rule, base_url, name, duty, link.get("href", "")))
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
