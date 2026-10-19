from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '1011',
 'domain': 'hrss.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_list_detail_gd_hrss_leaders_v1',
 'leader_region_selector': 'ul.list a[href][title]',
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
                     'max_detail_links': 0},
 'risk_flag': '列表页仅姓名，改为领导之窗两页名单加定点详情页解析；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.list a[href][title]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    """压缩广东人社厅页面中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def load_url(url: str) -> str:
    """在线读取领导之窗的分页或人物详情页。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_list_links(list_html: str, base_url: str) -> list[tuple[str, str]]:
    """读取领导之窗列表中的姓名详情链接。"""
    soup = BeautifulSoup(list_html, "html.parser")
    links: list[tuple[str, str]] = []
    for link in soup.select("ul.list a[href][title]"):
        name = clean_text(str(link.get("title", "")) or link.get_text(" ", strip=True))
        href = str(link.get("href", "")).strip()
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) and href:
            links.append((name, urljoin(base_url, href)))
    return links


def extract_duty(detail_html: str, name: str) -> str:
    """从领导详情页居中姓名职务段落提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text.startswith(name):
            continue
        duty = clean_text(text[len(name):])
        if duty and not duty.startswith("，") and "个人简历" not in duty:
            return duty.strip(" ，。；;、")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广东省人社厅领导之窗两页名单并读取定点详情页职务。"""
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；list=ul.list a[title] + index_2；detail=center_name_duty"
    links = parse_list_links(html, final_url)
    if not links:
        links = parse_list_links(load_url(page_url), page_url)
    second_page_url = urljoin(page_url, "index_2.html")
    links.extend(parse_list_links(load_url(second_page_url), second_page_url))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, detail_url in links:
        if name in seen:
            continue
        seen.add(name)
        detail_html = load_url(detail_url)
        duty = extract_duty(detail_html, name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
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
