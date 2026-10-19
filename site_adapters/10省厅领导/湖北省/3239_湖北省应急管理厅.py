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

PAGE_RULE = {'rule_id': '3239',
 'domain': 'yjt.hubei.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'hubei_emergency_management_duty_colon_name_v1',
 'leader_region_selector': 'html > body > div.wrap:nth-of-type(6) > div.content:nth-of-type(2) > div.grid.p1 > div.row '
                           '> ul.leader.h',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap:nth-of-type(6) > div.content:nth-of-type(2) > '
                                               'div.grid.p1 > div.row > ul.leader.h',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导信息 h4 直接列职务：姓名'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """湖北省应急管理厅领导信息页为“职务：姓名”的分组名单。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("ul.leader.h > li"):
        heading = item.select_one("h4")
        text = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = parts[0].strip().replace("（兼）", "").replace("(兼)", "")
        name = re.sub(r"\s+", "", parts[1]).strip()
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name):
            continue
        link = heading.find_parent("a", href=True) if heading else None
        href = str(link.get("href", "")).strip() if link else ""
        detail_url = urljoin(final_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
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
                "selector_summary": "ul.leader.h > li；h4职务：姓名",
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
