from __future__ import annotations

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

PAGE_RULE = {'rule_id': '2410',
 'domain': 'www.shrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shanghai_people_congress_role_rows_v1',
 'leader_region_selector': '.renyuan > .fuzhuren-row',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.zhurenpic a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.zhurenpic a[href]',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.renyuan > .fuzhuren-row',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.zhurenpic a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split()).strip()


def _clean_duty(value: str) -> str:
    return _clean_text(value.replace("：", "").replace(":", "")).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析上海市人大常委会主任之窗分组名单。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in soup.select(".renyuan > .fuzhuren-row"):
        duty_node = row.select_one(".fuzhuren-n p")
        duty = _clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for person in row.select(".fuzhuren"):
            name_node = person.select_one(".fuzhuren-name")
            name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            if not name:
                continue
            link = person.select_one(".zhurenpic a[href]")
            detail_url = urljoin(final_url, link.get("href", "")) if link else ""
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": final_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
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
