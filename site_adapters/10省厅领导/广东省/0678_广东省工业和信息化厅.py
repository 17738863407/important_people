from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0678',
 'domain': 'gdii.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'gdii_leader_work_paragraph_v1',
 'leader_region_selector': 'div.main.xl p',
 'name_selector': 'p冒号前',
 'duty_selector': 'p冒号后首个职务短语',
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
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div.main.xl p',
                     'name_selector': 'p冒号前',
                     'duty_selector': 'p冒号后首个职务短语',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线静态 HTML 正文段落包含完整领导分工'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(value: str) -> str:
    return clean_text(value).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    selector_summary = (
        "strategy=custom_parse_page；leader=div.main.xl p；"
        "name=p冒号前；duty=p冒号后至首个逗号/句号；detail=none；api_enabled=False"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select("div.main.xl p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        left, right = re.split(r"[:：]", text, maxsplit=1)
        name = normalize_name(left)
        if not (2 <= len(name) <= 4) or name in seen:
            continue
        duty = re.split(r"[，,。；;]", clean_text(right), maxsplit=1)[0].strip()
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
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
