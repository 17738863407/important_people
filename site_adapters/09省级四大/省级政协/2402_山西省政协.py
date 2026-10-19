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

PAGE_RULE = {'rule_id': '2402',
 'domain': 'www.shanxizx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'raw_http',
 'parser': 'custom_shanxi_zx_leader_nav_v1',
 'leader_region_selector': '.content-navlist-mok',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#barrierfree_container',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线HTML直接呈现政协领导分类导航'},
             'migration': {}}}


def clean_text(value: str) -> str:
    return " ".join((value or "").split())


def clean_name(value: str) -> str:
    return clean_text(value).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    base_url = final_url or page_rule["url"]

    for block in soup.select(".content-navlist-mok"):
        title = block.select_one(".content-navlist-title")
        duty = clean_text(title.get_text(" ", strip=True) if title else "")
        if not duty:
            continue
        for link in block.select(".content-navlist-con a[href]"):
            name = clean_name(link.get_text(" ", strip=True))
            if not name or name in seen:
                continue
            seen.add(name)
            detail_url = urljoin(base_url, link.get("href") or "")
            output_detail_url = "" if detail_url.rstrip("/") == base_url.rstrip("/") else detail_url
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": output_detail_url,
                    "evidence": duty,
                    "selector_summary": "政协领导分类导航链接",
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
