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

PAGE_RULE = {'rule_id': '3078',
 'domain': 'www.xizang.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xizang_government_leaders_v1',
 'leader_region_selector': '.list_con a.liTitle, .ldjs_con',
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
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body.lxz-body > div.g-main:nth-of-type(2) > '
                                               'div.lxz-content.centerWidth > div.zixun_con.clearfix:nth-of-type(2) > '
                                               'div.ldjs_con.lf:nth-of-type(2)',
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
    return re.sub(r"[\s\u200b]+", "", clean_text(value)).replace("·", "•")


def valid_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5•]{2,20}", value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析西藏自治区人民政府领导列表。"""
    soup = BeautifulSoup(html, "html.parser")
    current_node = soup.select_one(".ldjs_con .view")
    current_text = clean_text(current_node.get_text(" ", strip=True) if current_node else "")
    current_match = re.search(r"现任[^。]*。", current_text)
    current_evidence = current_match.group(0).removeprefix("现任").removesuffix("。").strip() if current_match else ""
    current_name_node = soup.select_one(".ldjs_con .name")
    current_name = normalize_name(current_name_node.get_text(" ", strip=True) if current_name_node else "")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".list_con a.liTitle[href]"):
        name_node = link.select_one(".name")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node else link.get("doctitle", ""))
        parts = list(link.stripped_strings)
        duty = clean_text(parts[0] if parts else "").rstrip("。")
        evidence = current_evidence if current_evidence and name == current_name else duty
        if not valid_name(name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": evidence,
                "detail_url": urljoin(page_rule["url"], link.get("href", "")),
                "evidence": evidence,
                "parser": "page_inline_xizang_government_leaders_v1",
                "selector_summary": ".list_con a.liTitle列表职务；当前主席详情现任句补全",
            }
        )
    return rows


if __name__ == "__main__":
    main()
