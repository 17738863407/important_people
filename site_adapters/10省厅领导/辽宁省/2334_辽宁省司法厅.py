from __future__ import annotations

import re
import sys
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

PAGE_RULE = {'rule_id': '2334',
 'domain': 'sft.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_guard_liaoning_justice_list_without_duty_v1',
 'leader_region_selector': '#zf_xxgkr .xxgk_tt',
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
 'risk_flag': '列表页仅有领导姓名和详情链接，职务由在线详情页补足',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#zf_xxgkr .xxgk_tt',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online_detail',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    """压缩网页文本中的空白字符。"""
    return re.sub(r"[\s\u00A0\u3000]+", " ", str(text or "")).strip()


def clean_name(text: str) -> str:
    """清理领导姓名。"""
    return re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip()


def load_detail_html(detail_url: str) -> str:
    """在线读取领导详情页。"""
    response = requests.get(
        detail_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_duty_from_detail(name: str, detail_html: str) -> tuple[str, str]:
    """从详情页个人简介中的“现任”句提取职务。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    text = clean_text(detail_soup.get_text(" ", strip=True))
    match = re.search(r"现任([^。；;]+)[。；;]?", text)
    if not match:
        return "", text[:160]
    duty = re.sub(r"[\s\u00A0\u3000]+", "", match.group(1)).strip(" ：:，,。；;")
    evidence = match.group(0).removeprefix("现任").rstrip("。；;")
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析辽宁省司法厅领导列表，并进入详情页补足职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select("#zf_xxgkr .oflow-hd dl"):
        link = item.select_one("dd.ldname a[href]") or item.select_one("a[href]")
        if not link:
            continue
        name = clean_name(link.get_text(" ", strip=True) or link.get("title", ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, link.get("href", ""))
        detail_html = load_detail_html(detail_url)
        duty, evidence = extract_duty_from_detail(name, detail_html)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_liaoning_justice_detail_v1",
                "selector_summary": "#zf_xxgkr .oflow-hd dl；detail_text=现任句",
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
