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

PAGE_RULE = {'rule_id': '1344',
 'domain': 'jyt.shanxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_inline',
 'collector': 'static_http',
 'parser': 'page_inline_shanxi_jyt_leader_card_v1',
 'leader_region_selector': 'html > body > div.box > div.index_box > div.ny_cont:nth-of-type(4) > '
                           'div.ny_cont_list_con:nth-of-type(3) > div.jytld.d_ib:nth-of-type(6)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.box > div.index_box > div.ny_cont:nth-of-type(4) > '
                                               'div.ny_cont_list_con:nth-of-type(3) > div.jytld.d_ib:nth-of-type(6)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页领导卡片已包含姓名、职务、分工和简介，不使用详情页解析'},
             'migration': {'source': 'inline_list_parser',
                           'verified_status': 'inline_list_verified',
                           'behavior_changed': True}}}


def normalize_name(text: str) -> str:
    """清理姓名中的全角空白和普通空格。"""
    return re.sub(r"\s+", "", text or "").strip()


def clean_text(text: str) -> str:
    """压缩页面文本中的空白字符。"""
    return re.sub(r"\s+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """直接从教育厅领导列表卡片抽取，不进入详情页链式解析。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select("div.jytld"):
        name_node = item.select_one("span > a")
        duty_node = item.select_one("span > font")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": page_rule.get("parser", ""),
            "selector_summary": "leader=div.jytld；name=span > a；duty=span > font",
        })
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
