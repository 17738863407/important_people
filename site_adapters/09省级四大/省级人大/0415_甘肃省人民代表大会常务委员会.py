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

PAGE_RULE = {'rule_id': '0415',
 'domain': 'district.ce.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ce_district_leader_parser_v1',
 'source_parser': 'table_person_parser_v1',
 'leader_region_selector': '.main .ren2, .main .TRS_Editor, .content .TRS_Editor, .trs_editor_view',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': [],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析正文领导名单，并在“任免动态”处停止。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content .TRS_Editor, .trs_editor_view")
    if not region:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        raw_text = " ".join(paragraph.get_text(" ", strip=True).split())
        if "任免动态" in raw_text:
            break
        match = re.fullmatch(r"(副主任|秘书长|主任)\s*([\u4e00-\u9fff·]{2,20})(?:简历)?", raw_text)
        if not match:
            continue
        duty, name = match.groups()
        name = re.sub(r"简历$", "", name)
        if name in seen:
            continue
        seen.add(name)
        link = paragraph.select_one("a[href]")
        detail_url = urljoin(final_url, link.get("href", "")) if link else ""
        if detail_url and not re.search(r"t\d+_\d+_\d+\.shtml(?:$|[?#])", detail_url):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule.get("parser", ""),
                "selector_summary": ".content .TRS_Editor首段领导名单，任免动态前截止",
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
