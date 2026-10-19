from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3380',
 'domain': 'zjt.hainan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_bracket_link_hainan_housing_department_leader_v1',
 'leader_region_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
 'name_selector': '链接文本方括号前姓名',
 'duty_selector': '链接文本方括号内职务',
 'detail_link_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
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
 'risk_flag': '领导链接已取消历史ddtab参数；必须限定在基本信息公开页的领导区域',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
                     'name_selector': '链接文本方括号前姓名',
                     'duty_selector': '链接文本方括号内职务',
                     'detail_link_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析海南省住房和城乡建设厅领导链接列表。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]"):
        text = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text("", strip=True))
        match = re.match(r"^([\u4e00-\u9fa5]{2,4})\[(.+?)\]$", text)
        if not match:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "领导链接文本姓名[职务]",
            }
        )
    return rows


if __name__ == "__main__":
    main()
