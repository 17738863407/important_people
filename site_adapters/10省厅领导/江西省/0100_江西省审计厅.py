from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0100',
 'domain': 'audit.jiangxi.gov.cn',
 'page_type': '图片名单型',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'online_jiangxi_audit_article_list_v1',
 'leader_region_selector': 'script articleList',
 'name_selector': 'articleList.title',
 'duty_selector': 'articleList.metadata.Subtitle',
 'detail_link_selector': 'articleList.urls.pc',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '领导信息存储在图片中',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'script articleList',
                     'name_selector': 'articleList.title',
                     'duty_selector': 'articleList.metadata.Subtitle',
                     'detail_link_selector': 'articleList.urls.pc',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面中的 script articleList 直接提供字段'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析江西省审计厅实时页面中的 articleList 领导数据。"""
    import json
    from urllib.parse import urljoin

    marker = "articleList:"
    start = html.find(marker)
    if start < 0:
        return []
    array_start = html.find("[", start)
    if array_start < 0:
        return []
    depth = 0
    array_end = -1
    in_string = False
    escape = False
    for index in range(array_start, len(html)):
        char = html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                array_end = index + 1
                break
    if array_end < 0:
        return []

    articles = json.loads(html[array_start:array_end])
    rows: list[dict[str, str]] = []
    for item in articles:
        name = str(item.get("title", "")).strip()
        metadata = item.get("metadata") or {}
        duty = str(metadata.get("Subtitle", "")).strip()
        urls_raw = str(item.get("urls", "")).strip()
        detail_url = ""
        if urls_raw:
            detail_url = urljoin(final_url or str(page_rule.get("url", "")), json.loads(urls_raw).get("pc", ""))
        if not name or not duty:
            continue
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "script articleList.title + metadata.Subtitle",
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
