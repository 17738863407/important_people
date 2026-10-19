from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2322',
 'domain': 'sft.fujian.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_fujian_sft_dropdown_v1',
 'leader_region_selector': '.leader_name_list .dropdown_menu li',
 'name_selector': 'a[href][title]的title首个空格前文本',
 'duty_selector': 'a[href][title]的title首个空格后文本',
 'detail_link_selector': 'a[href][title]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': ['.leader_name_list'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '领导目录a标签属性跨行排版，禁止使用依赖属性空格顺序的HTML正则',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader_name_list .dropdown_menu li',
                     'name_selector': 'a[href][title]的title首个空格前文本',
                     'duty_selector': 'a[href][title]的title首个空格后文本',
                     'detail_link_selector': 'a[href][title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.leader_name_list'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线更多领导下拉菜单 title 含姓名和职务'}}}


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> dict[str, str]:
    return {
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": duty,
        "confidence": "high",
        "parser": str(page_rule.get("parser", "")),
    }


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省司法厅领导详情页中的更多领导下拉名单。"""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = str(page_rule.get("url", "")) or final_url
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select(".leader_name_list .dropdown_menu li a[href][title]"):
        title = _clean_text(str(link.get("title") or ""))
        if not title or " " not in title:
            continue
        name, duty = title.split(" ", 1)
        name = name.strip()
        duty = duty.strip()
        if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        href = str(link.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(_make_record(page_rule, name, duty, detail_url))
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
