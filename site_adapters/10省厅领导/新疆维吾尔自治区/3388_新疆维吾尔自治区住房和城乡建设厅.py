from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3388',
 'domain': 'zjt.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_online_detail_xinjiang_housing_department_leader_v1',
 'leader_region_selector': '.leader-intro[href]',
 'name_selector': '.leader-intro span:first-child',
 'duty_selector': '在线详情岗位职责字段',
 'detail_link_selector': '.leader-intro[href]',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader-intro[href]',
                     'name_selector': '.leader-intro span:first-child',
                     'duty_selector': '在线详情岗位职责字段',
                     'detail_link_selector': '.leader-intro[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _parse_detail_duty(detail_html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    match = re.search(r"岗位职责\s+(.+?)\s+(?:分工\s+)?简历", text)
    if not match:
        return ""
    duty = re.sub(r"\s+", "", match.group(1))
    return duty.rstrip("，,；;。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区住房和城乡建设厅领导列表并从在线详情补职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leader-intro[href]"):
        first_span = link.select_one("span")
        name = re.sub(r"[\s\u3000]+", "", first_span.get_text("", strip=True) if first_span else "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            detail_html = response.text
        except requests.RequestException:
            continue
        duty = _parse_detail_duty(detail_html)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".leader-intro名单+详情岗位职责",
            }
        )
    return rows


if __name__ == "__main__":
    main()
