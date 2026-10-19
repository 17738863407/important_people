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

PAGE_RULE = {'rule_id': '0789',
 'domain': 'gxt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_inline_liaoning_gxt_bmld_list_detail_field_v1',
 'leader_region_selector': 'a[istitle="true"][href*="/bmld/"][title]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[istitle="true"][href*="/bmld/"][title]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '原文本段落解析为空；主页面仅列部门领导姓名链接，职务需从详情页.xxgk_ldlzw提取',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a[istitle="true"][href*="/bmld/"][title]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[istitle="true"][href*="/bmld/"][title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def load_detail_html(detail_url: str, referer: str) -> str:
    """实时在线采集详情页 HTML。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_detail_duty(detail_html: str) -> str:
    """从详情页职务字段提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    duty_node = soup.select_one(".xxgk_ldlzw")
    if duty_node:
        return clean_text(duty_node.get_text(" ", strip=True))
    match = re.search(r"现任(?P<duty>[^。；]+)", clean_text(soup.get_text(" ", strip=True)))
    return clean_text(match.group("duty")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析辽宁省工业和信息化厅部门领导列表及详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[istitle="true"][href*="/bmld/"][title]'):
        name = clean_name(str(link.get("title") or link.get_text(" ", strip=True)))
        href = str(link.get("href") or "")
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(source_url, href)
        duty = parse_detail_duty(load_detail_html(detail_url, source_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "主页面bmld领导链接取姓名；详情页.xxgk_ldlzw取职务",
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
