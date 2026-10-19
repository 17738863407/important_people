from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3378',
 'domain': 'zjt.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'gansu_housing_construction_leader_profiles_v1',
 'leader_region_selector': 'div#list',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#list',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 领导简介块直接列姓名和职务字段'}}}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """甘肃省住房和城乡建设厅机构领导页直接列领导简介和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div#list")
    if region is None:
        return []
    parser = str(page_rule["parser"])
    selector_summary = "领导简介块：姓名段落+职务字段"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name_node in region.find_all("div", class_="lead-name", recursive=False):
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        intro = name_node.find_next_sibling("div", class_="lead-intr")
        if not name or name in seen or intro is None:
            continue
        label = next(
            (node for node in intro.find_all("span") if clean_text(node.get_text(" ", strip=True)) in {"职务:", "职务：", "简历:", "简历："}),
            None,
        )
        duty_node = label.find_next_sibling("p") if label else None
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": parser,
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
