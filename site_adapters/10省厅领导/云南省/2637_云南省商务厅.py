from __future__ import annotations

import sys
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2637',
 'domain': 'swt.yn.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': 'yunnan_commerce_leader_division_paragraphs_v2',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_yunnan_commerce_leader_division_paragraphs_v1',
 'leader_region_selector': '.text p',
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
 'risk_flag': '主表旧入口显示页面不存在，需更新为官网当前领导分工正文页',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.text p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split())


def _clean_name(value: str) -> str:
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", _clean_text(value))


def _split_name_duty(prefix: str) -> tuple[str, str]:
    text = _clean_text(prefix)
    match = re.search(r"(党组|副厅长|厅长|纪检监察组|一级巡视员|二级巡视员)", text)
    if not match:
        return "", ""
    name = _clean_name(text[: match.start()])
    duty = _clean_text(text[match.start() :])
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析云南省商务厅领导分工段落。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in soup.select(".text p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        prefix = re.split(r"[：:]", text, maxsplit=1)[0]
        name, duty = _split_name_duty(prefix)
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "source_url": final_url,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "scope=.text p；fields=冒号前姓名与职务；exclude=冒号后分工内容；detail=none",
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
