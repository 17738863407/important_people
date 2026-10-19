from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0379',
 'domain': 'czt.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_gansu_czt_xzldxx_v1',
 'leader_region_selector': '.xzldxx .fxz a',
 'name_selector': '.xzldxx .fxz a p',
 'duty_selector': '.xzldxx .stitles',
 'detail_link_selector': '.xzldxx .fxz a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.xzldxx .fxz a',
                     'name_selector': '.xzldxx .fxz a p',
                     'duty_selector': '.xzldxx .stitles',
                     'detail_link_selector': '.xzldxx .fxz a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '动态 DOM 页面沿用 CSS 定位在线解析机构领导分组'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析甘肃省财政厅机构领导分组。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    container = soup.select_one(".xzldxx")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    current_duty = ""
    for node in container.find_all(["div"], recursive=False):
        classes = node.get("class", [])
        if "stitles" in classes:
            current_duty = re.sub(r"[\s\u3000\xa0]+", "", node.get_text(" ", strip=True))
            continue
        if "fxz" not in classes or not current_duty:
            continue
        for link in node.select("a[href]"):
            name_node = link.select_one("p")
            name = re.sub(r"[\s\u3000\xa0]+", "", name_node.get_text(" ", strip=True)) if name_node else ""
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                continue
            detail_url = urljoin(page_url, link.get("href") or "")
            if detail_url.rstrip("/") == page_url.rstrip("/"):
                detail_url = ""
            rows.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "detail_url": detail_url,
                    "evidence": current_duty,
                    "parser": parser,
                    "selector_summary": ".xzldxx .stitles+.fxz机构领导分组",
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
