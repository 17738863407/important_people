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

PAGE_RULE = {'rule_id': '0869',
 'domain': 'www.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hainan_gov_office_leader_li_v1',
 'leader_region_selector': 'ul li',
 'name_selector': 'ul li a[href]',
 'duty_selector': 'ul li',
 'detail_link_selector': 'ul li a[href]',
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
 'risk_flag': '页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul li',
                     'name_selector': 'ul li a[href]',
                     'duty_selector': 'ul li',
                     'detail_link_selector': 'ul li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for item in soup.select("ul li"):
        link = item.select_one("a[href]")
        if not link:
            continue
        text = clean_text(item.get_text(" ", strip=True))
        item_match = re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s+(.+?)\s+基本信息", text)
        if not item_match:
            continue
        name = clean_name(item_match.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        match = re.match(r"^[\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3}\s+(.+?)\s+基本信息", text)
        if not match:
            match = re.search(rf"{re.escape(name)}\s+(.+?)\s+基本信息", clean_name(text))
        duty = clean_text(match.group(1)) if match else ""
        if not duty or not re.search(r"秘书长|办公厅主任|党组成员|一级巡视员|副秘书长", duty):
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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
