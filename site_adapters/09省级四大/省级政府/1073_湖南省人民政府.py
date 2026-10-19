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

PAGE_RULE = {'rule_id': '1073',
 'domain': 'www.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_hunan_government_leaders_v1',
 'leader_region_selector': '#z_main .szf_l .szf_l_t .szf_l_h1',
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
 'risk_flag': '原选择器只指向秘书长列表并遗漏省长、副省长；改为省长/副省长/秘书长标题块解析；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#z_main .szf_l .szf_l_t .szf_l_h1',
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
    """压缩湖南省政府页面中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析湖南省人民政府首页省政府领导模块。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=#z_main .szf_l .szf_l_t .szf_l_h1；fields=职务标题/p姓名"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select("#z_main .szf_l .szf_l_t .szf_l_h1"):
        title_node = block.select_one(".szf_zw1, .szf_zw2")
        duty = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if duty not in {"省长", "副省长", "秘书长"}:
            continue
        for link in block.select("a[href]"):
            name_node = link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": page_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(page_url, str(link.get("href", ""))),
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
