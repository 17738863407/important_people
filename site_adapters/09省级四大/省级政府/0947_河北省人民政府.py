from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0947',
 'domain': 'www.hebei.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hebei_gov_leader_window_links_v1',
 'leader_region_selector': '',
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
 'risk_flag': '通用表格解析器未识别领导之窗链接；改为解析“职务+姓名”领导链接并排除领导活动新闻',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
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
    """压缩链接文本空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_link_text(text: str) -> tuple[str, str]:
    """解析“省委副书记，省长 姓名”“秘书长 姓名”格式。"""
    compact = clean_text(text)
    match = re.match(r"^(.+?)\s+([\u4e00-\u9fa5]{2,3})$", compact)
    if not match:
        return "", ""
    duty, name = match.groups()
    if "省长" not in duty and "秘书长" not in duty:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河北省人民政府领导之窗链接。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；selector=a；pattern=职务+空格+姓名"

    for link in soup.select("a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        name, duty = parse_link_text(text)
        if not name or name in seen:
            continue
        seen.add(name)
        href = str(link.get("href", ""))
        detail_url = urljoin(page_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == page_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
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
