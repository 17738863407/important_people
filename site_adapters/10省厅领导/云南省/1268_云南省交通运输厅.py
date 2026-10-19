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

PAGE_RULE = {'rule_id': '1268',
 'domain': 'jtyst.yn.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': 'yunnan_transport_leader_directory_detail_v2',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_yunnan_transport_leader_directory_detail_v2',
 'leader_region_selector': '#cat li',
 'name_selector': '#cat a[href]',
 'duty_selector': '详情页.lingdao-zhiwu',
 'detail_link_selector': '#cat a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '#cat a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '.wzbt',
                     'detail_duty_selector': '.lingdao-zhiwu',
                     'detail_content_selector': '.content_page',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新版名单页只直出姓名，须逐一读取详情页专用姓名与职务字段并交叉校验',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#cat li',
                     'name_selector': '#cat a[href]',
                     'duty_selector': '详情页.lingdao-zhiwu',
                     'detail_link_selector': '#cat a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty.strip(" ，。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按名单顺序读取人物详情页的专用姓名与职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；list=#cat a[href]；detail=.wzbt + .lingdao-zhiwu"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": page_url})

    for link in soup.select("#cat a[href]"):
        list_name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(page_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", list_name):
            continue
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "html.parser")
        name_node = detail_soup.select_one(".wzbt")
        duty_node = detail_soup.select_one(".lingdao-zhiwu")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if name != list_name:
            raise RuntimeError(f"名单姓名与详情姓名不一致：{list_name} != {name}")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
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
