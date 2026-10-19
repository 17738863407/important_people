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

PAGE_RULE = {'rule_id': '0726',
 'domain': 'gjw.gxzf.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'detail_follow',
 'collector': 'static_http',
 'parser': 'page_inline_guangxi_veterans_leader_detail_v1',
 'leader_region_selector': 'ul.ty-common-item',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '列表页只含姓名日期，职务在详情页姓名后括号内',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.ty-common-item',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'ul.ty-common-item a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导列表和详情页均为静态HTML'}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def load_detail_html(name: str, detail_url: str) -> str:
    """在线获取详情页 HTML。"""
    response = requests.get(
        detail_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text

def parse_detail_duty(name: str, detail_html: str) -> str:
    """从详情页姓名后的括号中提取职务。"""
    text = clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
    escaped_name = re.escape(name)
    patterns = [
        rf"{escaped_name}\s*[（(]\s*(?P<duty>[^）)]+?)\s*[）)]",
        r"打印\s*[（(]\s*(?P<duty>[^）)]+?)\s*[）)]\s*个人简历",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            duty = clean_text(match.group("duty"))
            return re.sub(r"[\[［]\s*兼\s*[\]］]", "", duty).strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广西壮族自治区退役军人事务厅领导之窗。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("ul.ty-common-item li a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        if name in seen or not detail_url:
            continue
        duty = parse_detail_duty(name, load_detail_html(name, detail_url))
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
                "selector_summary": "领导列表a取姓名和详情页；详情页姓名后括号取职务",
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
