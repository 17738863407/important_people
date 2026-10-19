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

PAGE_RULE = {'rule_id': '0230',
 'domain': 'www.chinatax.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_chinatax_leader_column_v1',
 'leader_region_selector': 'div.ldzl li dl',
 'name_selector': 'dt a',
 'duty_selector': 'dd p',
 'detail_link_selector': 'dt a[href]',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div.ldzl li dl',
                     'name_selector': 'dt a',
                     'duty_selector': 'dd p',
                     'detail_link_selector': 'dt a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """清理姓名中的全角空格。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", "")).strip()


def is_name_text(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_text(value)))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析领导专栏模块。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.ldzl li dl"):
        link = card.select_one("dt a[href]")
        duty_node = card.select_one("dd p")
        name = clean_text((link.get("title") if link else "") or (link.get_text(" ", strip=True) if link else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not is_name_text(name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href")) if link and final_url else "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_chinatax_leader_column_v1",
                "selector_summary": (
                    "strategy=custom_parse_page；leader=div.ldzl li dl；"
                    "name=dt a；duty=dd p；detail=dt a[href]；api_enabled=False"
                ),
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
