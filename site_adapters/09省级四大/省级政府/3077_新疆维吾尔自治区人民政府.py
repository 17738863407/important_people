from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3077',
 'domain': 'www.xinjiang.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang_government_leaders_v1',
 'leader_region_selector': '.zfxxgk_zfld_box',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.zfxxgk_container:nth-of-type(2) > '
                                               'div.zfxxgk_box:nth-of-type(2) > div.zfxxgk_right:nth-of-type(2) > '
                                               'div.zfxxgk_zfld_box',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value).replace(" · ", "·"))


def valid_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5·]{2,20}", value))


def add_row(rows: list[dict[str, str]], seen: set[str], page_rule: dict, name: str, evidence: str, href: str) -> None:
    name = normalize_name(name)
    evidence = clean_text(evidence)
    if not valid_name(name) or not evidence or name in seen:
        return
    seen.add(name)
    rows.append(
        {
            "organization": page_rule["organization"],
            "url": page_rule["url"],
            "name": name,
            "duty": evidence,
            "detail_url": urljoin(page_rule["url"], href),
            "evidence": evidence,
            "parser": "page_inline_xinjiang_government_leaders_v1",
            "selector_summary": ".zfxxgk_zfld_box；主席现任句，副主席/秘书长按分组",
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区人民政府领导列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    mayor_link = soup.select_one(".zfld_zx h3 a[href]")
    mayor_name = mayor_link.get_text(" ", strip=True) if mayor_link else ""
    mayor_description = soup.select_one(".zfld_zx .jl p")
    mayor_text = clean_text(mayor_description.get_text(" ", strip=True) if mayor_description else "")
    mayor_match = re.search(r"现任[^。]*。", mayor_text)
    mayor_title = soup.select_one(".zfld_zx .zfxxgk_zfld_tit span")
    mayor_evidence = mayor_match.group(0).removeprefix("现任").removesuffix("。") if mayor_match else clean_text(mayor_title.get_text(" ", strip=True) if mayor_title else "")
    add_row(rows, seen, page_rule, mayor_name, mayor_evidence, mayor_link.get("href", "") if mayor_link else "")

    vice_title = soup.select_one(".zfld_fzx .zfxxgk_zfld_tit span")
    vice_evidence = clean_text(vice_title.get_text(" ", strip=True) if vice_title else "")
    for link in soup.select(".zfld_fzx li p a[href]"):
        add_row(rows, seen, page_rule, link.get_text(" ", strip=True), vice_evidence, link.get("href", ""))

    secretary_title = soup.select_one(".zfld_msz .zfxxgk_zfld_tit span")
    secretary_evidence = clean_text(secretary_title.get_text(" ", strip=True) if secretary_title else "")
    for link in soup.select(".zfld_msz li p a[href]"):
        add_row(rows, seen, page_rule, link.get_text(" ", strip=True), secretary_evidence, link.get("href", ""))
    return rows


if __name__ == "__main__":
    main()
