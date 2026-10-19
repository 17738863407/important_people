from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0186',
 'domain': 'www.ce.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_ce_ministry_leader_group_cards_v1',
 'leader_region_selector': 'div.block div.title2 + ul.list1 li',
 'name_selector': 'li p a[href]',
 'duty_selector': 'parent div.title2 or parenthetical duty',
 'detail_link_selector': 'li p a[href]',
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
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'page_inline_group_cards',
 'locator': {'css': {'leader_region_selector': 'div.block div.title2 + ul.list1 li',
                     'name_selector': 'li p a[href]',
                     'duty_selector': 'parent div.title2 or parenthetical duty',
                     'detail_link_selector': 'li p a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线人物库卡片已包含领导分组和姓名，无需接口'},
             'migration': {'source': 'online_static_html_builder',
                           'verified_status': 'online_pending',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def split_name_duty(text: str, fallback_duty: str) -> tuple[str, str]:
    import re

    raw = clean_text(text)
    match = re.match(r"^([^（(]+)[（(]([^）)]+)[）)]$", raw)
    if match:
        return clean_text(match.group(1)).replace(" ", ""), clean_text(match.group(2))
    return raw.replace(" ", ""), clean_text(fallback_duty.split("、", 1)[0])


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    block = soup.select_one("div.con_left div.block")
    if not block:
        return rows
    for title in block.select("div.title2"):
        group_duty = clean_text(title.get_text(" ", strip=True))
        group_list = title.find_next_sibling("ul", class_="list1")
        if not group_list:
            continue
        for item in group_list.select("li"):
            link = item.select_one("p a[href]")
            if not link:
                continue
            name, duty = split_name_duty(link.get_text(" ", strip=True), group_duty)
            if not name or not duty:
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "source_text": f"{group_duty} {clean_text(link.get_text(' ', strip=True))}",
                    "method": page_rule["parser"],
                    "note": (
                        "strategy=custom_parse_page；leader=div.block title2 + ul.list1 li；"
                        "name=p a；duty=parenthetical_or_group_first_role；detail=p a；api_enabled=False"
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
