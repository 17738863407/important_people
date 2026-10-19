from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2874',
 'domain': 'whly.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_liaoning_culture_list_detail_v1',
 'leader_region_selector': '.provincial-leaders-inner',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def load_detail_duty(detail_url: str) -> str:
    try:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    duty_node = soup.select_one(".xxgk_ldlzw a[title]")
    if duty_node:
        return clean_text(duty_node.get("title") or duty_node.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict] = []
    seen: set[str] = set()
    for item in soup.select(".provincial-leaders-inner dl"):
        link = item.find("a", href=True)
        name_node = item.select_one("dd a")
        image = item.find("img", alt=True)
        name = clean_text((name_node.get_text(" ", strip=True) if name_node else "") or (image.get("alt") if image else ""))
        if not link or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, link["href"])
        duty = load_detail_duty(detail_url)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "列表姓名链接+详情.xxgk_ldlzw职务",
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
