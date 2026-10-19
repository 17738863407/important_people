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

PAGE_RULE = {'rule_id': '0778',
 'domain': 'gxt.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_inline_fujian_gxt_leader_dropdown_detail_v1',
 'leader_region_selector': '.dropdown_menu a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.dropdown_menu a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '当前页仅显示单名领导，需从更多领导菜单补齐其余详情页',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.dropdown_menu a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.dropdown_menu a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线静态详情页使用既有 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(name: str) -> str:
    """清理姓名中的排版空白。"""
    return clean_text(name).replace(" ", "")


def load_detail_html(detail_url: str, referer: str, current_html: str) -> str:
    """实时在线采集详情页 HTML。"""
    if detail_url.rstrip("/") == referer.rstrip("/"):
        return current_html

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


def parse_detail(html: str) -> tuple[str, str]:
    """从单名领导详情页提取姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_pic = soup.select_one(".leader_pic")
    link = leader_pic.select_one("a[title]") if leader_pic else None
    name = clean_name(str(link.get("title") if link else ""))
    duty_node = leader_pic.find_next("p") if leader_pic else None
    duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析福建省工业和信息化厅领导介绍下拉菜单及详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".dropdown_menu a[href]"):
        menu_name = clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", menu_name):
            continue
        detail_url = urljoin(source_url, href)
        try:
            detail_html = load_detail_html(detail_url, source_url, html)
        except requests.RequestException:
            continue
        name, duty = parse_detail(detail_html)
        if not name:
            name = menu_name
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        seen.add(name)
        output_detail_url = detail_url
        if output_detail_url.rstrip("/") == source_url.rstrip("/"):
            output_detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": output_detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".dropdown_menu领导菜单取链接；详情页.leader_pic后p取职务",
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
