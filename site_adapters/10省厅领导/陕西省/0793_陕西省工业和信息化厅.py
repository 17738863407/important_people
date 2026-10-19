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

PAGE_RULE = {'rule_id': '0793',
 'domain': 'gxt.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'chrome_cdp',
 'extract_mode': 'list_direct',
 'collector': 'chrome_cdp',
 'parser': 'page_inline_shaanxi_gxt_ldy_left_item_v1',
 'leader_region_selector': 'a.ldy-left-item[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a.ldy-left-item[href]',
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
 'risk_flag': '机构领导入口通过meta Refresh跳转首位领导详情，使用Chrome获取完整侧栏名单',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a.ldy-left-item[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a.ldy-left-item[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析陕西省工业和信息化厅领导成员侧栏列表。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a.ldy-left-item[href]"):
        cells = [clean_text(div.get_text(" ", strip=True)) for div in link.select("div")]
        cells = [cell for cell in cells if cell]
        if len(cells) < 2:
            continue
        name = clean_name(cells[0])
        duty = clean_text(cells[1])
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "a.ldy-left-item内前两个div取姓名和职务",
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
