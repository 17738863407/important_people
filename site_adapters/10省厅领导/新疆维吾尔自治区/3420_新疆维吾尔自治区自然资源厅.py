from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3420',
 'domain': 'zrzyt.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_lditem_xinjiang_natural_resources_leader_v1',
 'leader_region_selector': '.kyy_textR .lditem',
 'name_selector': 'p.ld-name',
 'duty_selector': 'p.ld-name后的简介首句',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.kyy_textR .lditem',
                     'name_selector': 'p.ld-name',
                     'duty_selector': 'p.ld-name后的简介首句',
                     'detail_link_selector': '',
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


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()


def _extract_duty(text: str) -> str:
    text = _clean_text(text)
    match = re.match(r"^(.+?。)(?:男|女|$)", text)
    duty = match.group(1) if match else text.split("。", 1)[0]
    return duty.rstrip("。；;，, ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区自然资源厅领导之窗人物块。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".kyy_textR .lditem"):
        name_el = item.select_one("p.ld-name")
        if not name_el:
            continue
        name = _clean_text(name_el.get_text(" ", strip=True))
        duty_text = ""
        for para in name_el.find_all_next("p"):
            if para is name_el:
                continue
            text = _clean_text(para.get_text(" ", strip=True))
            if text:
                duty_text = text
                break
        duty = _extract_duty(duty_text)
        if not name or not duty or name in seen:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,10}", name):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".kyy_textR .lditem",
            }
        )
    return rows


if __name__ == "__main__":
    main()
