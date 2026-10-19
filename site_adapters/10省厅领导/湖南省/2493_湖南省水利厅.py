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

PAGE_RULE = {'rule_id': '2493',
 'domain': 'slt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'leader_member_link_list_hunan_hydrology_v1',
 'leader_region_selector': '领导成员列表',
 'name_selector': '领导链接文本姓名',
 'duty_selector': '领导链接文本职务',
 'detail_link_selector': '领导成员a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.g-box:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 中使用原精确范围解析领导链接'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析湖南水文领导成员链接列表。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("html > body > div.g-box:nth-of-type(1)")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for link in region.select(".leadlist-b ul > a[href]"):
        name_node = link.select_one("li > p")
        duty_node = link.select_one("li > span")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        parsed_detail = urlparse(detail_url)
        if (
            parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith((".shtml", ".html", ".htm"))
        ):
            detail_url = ""
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "领导成员链接文本：姓名+职务",
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
