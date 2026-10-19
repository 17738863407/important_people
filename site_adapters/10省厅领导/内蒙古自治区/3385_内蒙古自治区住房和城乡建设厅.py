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

PAGE_RULE = {'rule_id': '3385',
 'domain': 'zjt.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inner_mongolia_housing_leader_detail_with_colleagues_v1',
 'leader_region_selector': '.ConLingls, .ConLinglxx li',
 'name_selector': '.ConLingls strong#cname 或 .ldname a',
 'duty_selector': '.ConLingls span 或 li em',
 'detail_link_selector': '.ConLinglxx .ldname a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.BuMen:nth-of-type(4)',
                     'name_selector': '.ConLingls strong#cname 或 .ldname a',
                     'duty_selector': '.ConLingls span 或 li em',
                     'detail_link_selector': '.ConLinglxx .ldname a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析内蒙古自治区住房和城乡建设厅领导详情页及同事列表。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    current_name_node = soup.select_one(".ConLingls strong#cname")
    current_duty_node = soup.select_one(".ConLingls span")
    if current_name_node:
        name = re.sub(r"[\s\u00a0\u3000]+", "", current_name_node.get_text("", strip=True))
        duty = re.sub(r"[\s\u00a0\u3000]+", "", current_duty_node.get_text("", strip=True)) if current_duty_node else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".ConLingls当前领导+.ConLinglxx同事列表",
            }
        )
        seen.add(name)

    for item in soup.select(".ConLinglxx li"):
        link = item.select_one(".ldname a[href]")
        duty_node = item.select_one("em")
        if not link:
            continue
        name = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text("", strip=True))
        duty = re.sub(r"[\s\u00a0\u3000]+", "", duty_node.get_text("", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
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
                "selector_summary": ".ConLingls当前领导+.ConLinglxx同事列表",
            }
        )
    return rows


if __name__ == "__main__":
    main()
