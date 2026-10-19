from __future__ import annotations

import sys
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2644',
 'domain': 'sxdofcom.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shaanxi_commerce_leader_introduce_cards_v1',
 'leader_region_selector': '.leader-info .leader-introduce',
 'name_selector': '.detail .name',
 'duty_selector': '.detail .status',
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
 'locator': {'css': {'leader_region_selector': '.leader-info .leader-introduce',
                     'name_selector': '.detail .name',
                     'duty_selector': '.detail .status',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split())


def _clean_name(value: str) -> str:
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", _clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析陕西省商务厅领导信息卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in soup.select(".leader-info .leader-introduce"):
        name_node = item.select_one(".detail .name")
        duty_node = item.select_one(".detail .status")
        name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.leader-info .leader-introduce；name=.name；duty=.status；detail=；api_enabled=False",
                "order": str(len(records) + 1),
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
