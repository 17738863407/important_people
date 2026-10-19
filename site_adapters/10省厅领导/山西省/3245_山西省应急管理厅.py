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

PAGE_RULE = {'rule_id': '3245',
 'domain': 'yjt.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ShanxiEmergencyLeaderListParser_v1',
 'leader_region_selector': '.ldxx_list a[title]',
 'name_selector': 'title before ideographic space',
 'duty_selector': 'title after ideographic space',
 'detail_link_selector': '.ldxx_list a[title]',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldxx_list a[title]',
                     'name_selector': 'title before ideographic space',
                     'duty_selector': 'title after ideographic space',
                     'detail_link_selector': '.ldxx_list a[title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(text: str) -> str:
    return _clean_text(text).replace(" ", "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析山西省应急管理厅领导信息列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for link in soup.select(".ldxx_list a[title]"):
        raw_title = link.get("title", "") or link.get_text(" ", strip=True)
        if "\u3000" in raw_title:
            raw_name, raw_duty = raw_title.split("\u3000", 1)
        else:
            parts = _clean_text(raw_title).split(" ", 1)
            if len(parts) != 2:
                continue
            raw_name, raw_duty = parts
        name = _clean_name(raw_name)
        duty = _clean_text(raw_duty)
        if not name or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.ldxx_list a[title]；name=title全角空白前文本；duty=title全角空白后文本；detail=a[href]",
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
