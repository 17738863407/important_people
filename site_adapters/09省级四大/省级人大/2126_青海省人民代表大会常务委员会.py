from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2126',
 'domain': 'www.qhrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_qinghai_rd_zrzc_grouped_cards_v1',
 'leader_region_selector': '.zrzc_cloumn1 .leader_cloumn',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': '.zrzc_cloumn1 .leader_cloumn',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def _name_without_small(name_node: Tag) -> str:
    parts = []
    for child in name_node.children:
        if isinstance(child, Tag) and child.name == "small":
            continue
        if isinstance(child, Tag):
            parts.append(child.get_text(" ", strip=True))
        else:
            parts.append(str(child).strip())
    return "".join(" ".join(part for part in parts if part).split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析青海省人大常委会主任之窗分组卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in soup.select(".zrzc_cloumn1 .leader_cloumn"):
        duty_node = group.select_one(".leader_tit")
        if not duty_node:
            continue
        duty = " ".join(duty_node.get_text(" ", strip=True).split())
        for link in group.select("a[href]"):
            name_node = link.select_one("p")
            if not name_node:
                continue
            name = _name_without_small(name_node)
            if not name or not duty:
                continue
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
                    "detail_url": urljoin(final_url, link.get("href", "")),
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
