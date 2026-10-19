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

PAGE_RULE = {'rule_id': '0753',
 'domain': 'www.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guizhou_gov_leader_window_v1',
 'leader_region_selector': 'div.ldzcBox',
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
 'risk_flag': '领导区为首页卡片分组，需按h1区分副省长与秘书长',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.ldzcBox',
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
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """姓名字段去除网页排版空格。"""
    return clean_text(value).replace(" ", "")


def build_detail_url(source_url: str, href: str) -> str:
    """仅保留真实独立人物详情链接。"""
    if not href or href.startswith(("#", "javascript:")):
        return ""
    detail_url = urljoin(source_url, href)
    return "" if detail_url.rstrip("/") == source_url.rstrip("/") else detail_url


def build_row(
    page_rule: dict[str, object],
    source_url: str,
    name: str,
    duty: str,
    detail_url: str,
) -> dict[str, str]:
    """生成统一输出记录。"""
    return {
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": duty,
        "confidence": "high",
        "parser": str(page_rule.get("parser", "")),
        "selector_summary": "div.ldzcBox领导之窗；省长卡片取姓名职务，副省长/秘书长按h1分组取姓名",
    }


def parse_top_leader(box: BeautifulSoup, page_rule: dict[str, object], source_url: str) -> dict[str, str] | None:
    """解析左侧省长卡片。"""
    link = box.select_one(".ld_info a.ld_mc[href]")
    if not link:
        return None
    text = clean_text(link.get_text(" ", strip=True))
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,6})\s+(?P<duty>.+)$", text)
    if not match:
        return None
    name = clean_name(match.group("name"))
    duty = clean_text(match.group("duty"))
    detail_url = build_detail_url(source_url, str(link.get("href") or ""))
    return build_row(page_rule, source_url, name, duty, detail_url)


def parse_grouped_leaders(box: BeautifulSoup, page_rule: dict[str, object], source_url: str) -> list[dict[str, str]]:
    """解析右侧副省长、秘书长分组列表。"""
    rows: list[dict[str, str]] = []
    current_duty = ""
    leader_list = box.select_one(".ld_list")
    if not leader_list:
        return rows

    for node in leader_list.find_all(["h1", "li"], recursive=True):
        if node.name == "h1":
            current_duty = clean_text(node.get_text(" ", strip=True)).rstrip("：:")
            continue
        if node.name != "li" or not current_duty:
            continue

        link = node.select_one("a[href]")
        name = clean_name(node.get_text(" ", strip=True))
        if not link or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = build_detail_url(source_url, str(link.get("href") or ""))
        rows.append(build_row(page_rule, source_url, name, current_duty, detail_url))

    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析贵州省人民政府政务公开页领导之窗。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    box = soup.select_one("div.ldzcBox")
    if not box:
        return []

    rows: list[dict[str, str]] = []
    top_row = parse_top_leader(box, page_rule, source_url)
    if top_row:
        rows.append(top_row)
    rows.extend(parse_grouped_leaders(box, page_rule, source_url))
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
