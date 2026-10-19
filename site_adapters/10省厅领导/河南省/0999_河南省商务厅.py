from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0999',
 'domain': 'hnsswt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_commerce_limited_leader_pages_v1',
 'leader_region_selector': '.tld .name-list a[href]',
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
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '通用空选择器解析为空，改为厅领导链接白名单并读取顶部职务；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.tld .name-list a[href]',
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


def clean_text(value: str) -> str:
    """压缩商务厅领导页文本空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def fetch_detail_text(url: str) -> str:
    """读取厅领导详情页文本。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".tld") or soup
    for navigation in node.select(".name-list"):
        navigation.decompose()
    return clean_text(node.get_text(" ", strip=True))


def extract_duty(detail_text: str, name: str) -> str:
    """从“厅领导 姓名 职务 领导简介”顶部结构提取职务。"""
    spaced_name = r"\s*".join(map(re.escape, name))
    match = re.search(rf"厅领导\s+{spaced_name}\s+(.+?)\s+领导简介", detail_text)
    if not match:
        match = re.search(rf"{spaced_name}\s*[，,]\s*(.+?)\s*[，,]\s*(?:男|女)", detail_text)
    if not match:
        return ""
    return clean_text(match.group(1)).strip("，。；;、 ")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河南省商务厅厅领导列表，并受限读取每个领导页顶部职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；selector=.tld .name-list a[href]；detail_pattern=厅领导姓名职务领导简介"

    for link in soup.select(".tld .name-list a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(page_url, str(link.get("href", "")))
        try:
            detail_text = fetch_detail_text(detail_url)
            duty = extract_duty(detail_text, name)
        except Exception:
            continue
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "order": len(rows) + 1,
                "detail_url": detail_url,
                "evidence": duty,
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
