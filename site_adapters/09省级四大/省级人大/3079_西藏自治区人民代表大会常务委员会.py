from __future__ import annotations

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

PAGE_RULE = {'rule_id': '3079',
 'domain': 'www.xizangrd.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'TibetPeopleCongressLeaderWindowParser_v1',
 'leader_region_selector': '.ldImg .detail a[href]',
 'name_selector': '链接文本或 b',
 'duty_selector': 'href路径分组',
 'detail_link_selector': '.ldImg .detail a[href]',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ldImg .detail a[href]',
                     'name_selector': '链接文本或 b',
                     'duty_selector': 'href路径分组',
                     'detail_link_selector': '.ldImg .detail a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return " ".join((text or "").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析西藏人大网首页领导之窗。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for link in soup.select(".ldImg .detail a[href]"):
        href = link.get("href", "")
        if href.startswith("/zr/"):
            duty = "主任"
            name_node = link.select_one("b")
            name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        elif href.startswith("/fzr/"):
            duty = "副主任"
            name = _clean_text(link.get_text(" ", strip=True))
        elif href.startswith("/msz/"):
            duty = "秘书长"
            name = _clean_text(link.get_text(" ", strip=True))
        else:
            continue
        if not name:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, href),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.ldImg .detail a[href]；姓名取链接文本或b；职务由可验证的href分组确定；详情链接取当前人物链接",
            }
        )
    return records


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
