from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析福建省政府领导分组卡片。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one('[role="viewlist"][des="省政府领导"]')
    if root is None:
        return []

    rows: list[dict[str, str]] = []
    source_url = final_url or str(page_rule.get("url", ""))
    seen: set[tuple[str, str]] = set()

    for group in root.select(".szf_tit1"):
        label_node = group.select_one(".szf_tit_l, .szf_tit_l1")
        duty = clean_text(label_node.get_text(" ", strip=True) if label_node else "").rstrip("：:")
        if not duty:
            continue
        for link in group.select("a[href]"):
            name_node = link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
            name = name.replace("\xa0", "").replace("\u2002", "").replace("\u2003", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            href = str(link.get("href") or "")
            detail_url = urljoin(source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
            if detail_url.rstrip("/") == source_url.rstrip("/"):
                detail_url = ""
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_inline_fujian_gov_leader_groups_v1",
                }
            )
    return rows


PAGE_RULE = {'rule_id': '0575',
 'domain': 'www.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_fujian_gov_leader_groups_v1',
 'leader_region_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1',
 'name_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1 a[href] p',
 'duty_selector': '[role="viewlist"][des="省政府领导"] .szf_tit_l, [role="viewlist"][des="省政府领导"] .szf_tit_l1',
 'detail_link_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1 a[href]',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1',
                     'name_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1 a[href] p',
                     'duty_selector': '[role="viewlist"][des="省政府领导"] .szf_tit_l, [role="viewlist"][des="省政府领导"] .szf_tit_l1',
                     'detail_link_selector': '[role="viewlist"][des="省政府领导"] .szf_tit1 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


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
