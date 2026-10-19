from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3191',
 'domain': 'yjgl.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'gansu_emergency_management_leader_window_v1',
 'leader_region_selector': '领导之窗正文 begin-end',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '正文含下载/分享等页面功能文本，需限定领导之窗 begin-end',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.box_cont:nth-of-type(7)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 的领导之窗正文直接列姓名职务'}}}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析甘肃省应急管理厅领导之窗正文。"""
    soup = BeautifulSoup(html, "html.parser")
    parser = str(page_rule["parser"])
    selector = str(page_rule["leader_region_selector"])
    regions = soup.select("div.box_cont")
    region = next(
        (node for node in regions if "甘肃省应急管理厅" in node.get_text(" ", strip=True)),
        soup,
    )
    text = clean_text(region.get_text(" ", strip=True))
    pattern = re.compile(
        r"(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>甘肃省应急管理厅.*?)(?=\s+[\u4e00-\u9fff·]{2,4}\s+甘肃省应急管理厅|\s+分享：|\s+【WORD下载】|$)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        name = match.group("name")
        duty = clean_text(match.group("duty")).strip("，,；;。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": parser,
                "selector_summary": selector,
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
