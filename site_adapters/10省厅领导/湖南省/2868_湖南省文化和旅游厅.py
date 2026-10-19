from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2868',
 'domain': 'whhlyt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'hunan_culture_tourism_leader_list_v1',
 'leader_region_selector': 'ul.doc-list-leader',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'list_detail_links'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'html > body > div.main.main-list:nth-of-type(3) > '
                                               'div.list-wrap:nth-of-type(2) > div.list-main:nth-of-type(2) > '
                                               'div.content-list:nth-of-type(2) > ul.doc-list-leader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '厅领导列表直接列出姓名和完整职务'},
             }}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按原 doc-list-leader 列表顺序抽取在线姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = (
        "html > body > div.main.main-list:nth-of-type(3) > "
        "div.list-wrap:nth-of-type(2) > div.list-main:nth-of-type(2) > "
        "div.content-list:nth-of-type(2) > ul.doc-list-leader"
    )
    region = soup.select_one(selector)
    rows: list[dict[str, str]] = []
    if region is None:
        return rows
    for item in region.select(":scope > li"):
        name_node = item.select_one("p.ld-name")
        detail_node = item.select_one("p.listtxt a.msgoo[href]")
        duty_node = item.select_one("div.ld-msg > p:not(.ld-name):not(.listtxt) span")
        if not (name_node and duty_node):
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"[（(]兼[）)]", "", re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True))).strip("，、 ")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        detail_url = ""
        if detail_node:
            candidate = urljoin(final_url, detail_node.get("href") or "")
            same_host = urlparse(candidate).netloc.lower() == urlparse(final_url).netloc.lower()
            real_person_page = bool(re.search(r"/t\d+_\d+\.html$", urlparse(candidate).path))
            if same_host and real_person_page:
                detail_url = candidate
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "原 ul.doc-list-leader 姓名、职务及详情链接",
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
