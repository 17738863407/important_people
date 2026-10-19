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

PAGE_RULE = {'rule_id': '2459',
 'domain': 'sjt.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V004_card_person_v1',
 'leader_region_selector': '.leader-info, .other-leader .list',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leader-info, .other-leader .list',
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
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return "".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析陕西省审计厅领导信息页。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    main = soup.select_one(".leader-info")
    if main:
        name_node = main.select_one(".leader-detailInfo .name")
        duty_node = main.select_one(".leader-detailInfo .detail")
        if name_node and duty_node:
            name = _clean_name(name_node.get_text(" ", strip=True))
            duty = _clean_text(duty_node.get_text(" ", strip=True))
            detail_link = main.select_one(".leader-detailInfo a[href]")
            href = detail_link.get("href", "").strip() if detail_link else ""
            if name and duty:
                seen.add(name)
                rows.append(
                    {
                        "name": name,
                        "duty": "",
                        "detail_url": urljoin(final_url or source_url, href) if href else "",
                        "evidence": duty,
                        "parser": "custom_shaanxi_audit_leader_cards_v1",
                        "selector_summary": ".leader-info；p.name+p.detail",
                        "order": str(len(rows) + 1),
                    }
                )

    for link in soup.select(".other-leader .list a[href]"):
        name_node = link.select_one("p.name")
        duty_node = link.select_one("p:not(.name)")
        if not name_node or not duty_node:
            continue
        name = _clean_name(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        href = link.get("href", "").strip()
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(final_url or source_url, href) if href else "",
                "evidence": duty,
                "parser": "custom_shaanxi_audit_leader_cards_v1",
                "selector_summary": ".other-leader .list a；p.name+p",
                "order": str(len(rows) + 1),
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
