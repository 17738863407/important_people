from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0406',
 'domain': 'dct.jiangxi.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'online_jxdct_listdata_v1',
 'leader_region_selector': 'li[aria-artlist]',
 'name_selector': 'li[aria-artlist] a[aria-arttitle]',
 'duty_selector': 'script listData.articleList.summary',
 'detail_link_selector': 'li[aria-artlist] a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'li[aria-artlist]',
                     'name_selector': 'li[aria-artlist] a[aria-arttitle]',
                     'duty_selector': 'script listData.articleList.summary',
                     'detail_link_selector': 'li[aria-artlist] a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面脚本解析 listData.articleList'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析江西省文化和旅游厅领导信息列表数据。"""
    import json
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", ""))
    parser = str(page_rule.get("parser", ""))
    match = re.search(r"\barticleList\s*:\s*", html)
    if not match:
        return []
    articles, _ = json.JSONDecoder().raw_decode(html, match.end())
    rows: list[dict[str, str]] = []
    for article in articles:
        title_html = str(article.get("title") or article.get("showTitle") or "")
        name = re.sub(r"[\s\u3000\xa0]+", "", BeautifulSoup(title_html, "html.parser").get_text(" ", strip=True))
        duty = re.sub(r"[\s\u3000\xa0]+", "", str(article.get("summary") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        if not duty:
            continue
        urls_text = str(article.get("urls") or "")
        try:
            detail_path = str(json.loads(urls_text).get("pc") or "")
        except (json.JSONDecodeError, AttributeError):
            detail_path = ""
        detail_url = urljoin(final_url or page_url, detail_path) if detail_path else ""
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
                "selector_summary": "li[aria-artlist]+listData.summary",
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
