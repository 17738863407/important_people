from __future__ import annotations

import re
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2574',
 'domain': 'sthjt.jiangxi.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'leader_channel_tree_article_json_jx_env_v2',
 'leader_region_selector': 'channelTreeTag中col42152的可见子栏目',
 'name_selector': 'articleList.title',
 'duty_selector': 'articleList.metadata.Subtitle',
 'detail_link_selector': 'articleList.urls.pc',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
                     'detail_collector_type': 'chrome_cdp',
                     'candidate_links': []},
 'risk_flag': '入口列表tbody由脚本动态加载，使用页面公开channelTreeTag与articleJson',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#tableList > table',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'channel_tree': 'channelTreeTag.children',
                     'leader_channel_code': 'col42152',
                     'data_path': '子栏目articleJson首条含metadata.Subtitle的记录'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按公开栏目树顺序解析可见领导子栏目的articleList JSON。"""
    import json

    import requests

    organization = str(page_rule["organization"])
    page_url = str(page_rule["url"])
    marker_match = re.search(r"\bvar\s+channelTreeTag\s*=\s*", html)
    if marker_match is None:
        return []
    try:
        channel_tree, _ = json.JSONDecoder().raw_decode(html, marker_match.end())
    except json.JSONDecodeError:
        return []

    stack = [channel_tree]
    leader_channel: dict[str, object] | None = None
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        if current.get("code") == "col42152":
            leader_channel = current
            break
        children = current.get("children")
        if isinstance(children, list):
            stack.extend(reversed(children))
    if leader_channel is None:
        return []

    parts = urlsplit(final_url or page_url)
    api_base = urlunsplit(("http", parts.netloc, "/", "", ""))
    headers = {"Referer": final_url or page_url, "User-Agent": "Mozilla/5.0"}
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for child in leader_channel.get("children", []):
        if not isinstance(child, dict) or str(child.get("showOrNot")) != "1":
            continue
        article_json = str(child.get("articleJson") or "")
        if not article_json:
            continue
        response = requests.get(urljoin(api_base, article_json), headers=headers, timeout=30)
        response.raise_for_status()
        articles = response.json()
        article = next(
            (
                item
                for item in articles
                if isinstance(item, dict)
                and isinstance(item.get("metadata"), dict)
                and str(item["metadata"].get("Subtitle") or "").strip()
            ),
            None,
        )
        if article is None:
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", str(article.get("title") or child.get("name") or ""))
        duty = re.sub(r"[\s\u3000\xa0]+", "", str(article["metadata"].get("Subtitle") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty or name in seen:
            continue
        urls_text = str(article.get("urls") or "")
        try:
            detail_path = str(json.loads(urls_text).get("pc") or "")
        except (json.JSONDecodeError, AttributeError):
            detail_path = ""
        detail_url = urljoin(final_url or page_url, detail_path) if detail_path else ""
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "channelTreeTag可见子栏目顺序+articleJson首条metadata.Subtitle",
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
