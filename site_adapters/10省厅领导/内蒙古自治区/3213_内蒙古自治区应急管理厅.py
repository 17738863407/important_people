from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '3213',
 'domain': 'yjglt.nmg.gov.cn',
 'page_type': '人物表格页',
 'structure_group': 'problem_table_compound_person',
 'reuse_scope': 'page_structure',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'InnerMongoliaEmergencyLeaderCardParser_v1',
 'leader_region_selector': '.leader-data',
 'name_selector': '.data-name',
 'duty_selector': '.data-post + .data-duty',
 'detail_link_selector': '.data-id',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader-data',
                     'name_selector': '.data-name',
                     'duty_selector': '.data-post + .data-duty',
                     'detail_link_selector': '.data-id',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '现行页面 HTML 隐藏数据容器已包含领导姓名、职务和分工'}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析内蒙古自治区应急管理厅领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(".leader-data"):
        name = _clean_text(card.select_one(".data-name").get_text(" ", strip=True) if card.select_one(".data-name") else "")
        post = _clean_text(card.select_one(".data-post").get_text(" ", strip=True) if card.select_one(".data-post") else "")
        detail_id = _clean_text(card.select_one(".data-id").get_text(" ", strip=True) if card.select_one(".data-id") else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, detail_id) if detail_id else ""
        records.append(
            {
                "name": name,
                "duty": post,
                "detail_url": detail_url,
                "evidence": post,
                "parser": rule["parser"],
                "selector_summary": "strategy=custom_parse_page；leader=.leader-data；name=.data-name；duty=.data-post；detail=.data-id",
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
