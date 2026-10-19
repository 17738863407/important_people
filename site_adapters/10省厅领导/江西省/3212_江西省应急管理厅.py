from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3212',
 'domain': 'yjglt.jiangxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '官方栏目JSON接口',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'extract_mode': 'api_direct',
 'collector': 'custom_api_http',
 'parser': 'jiangxi_emergency_management_leader_api_v2',
 'leader_region_selector': 'api:/queryList results[]',
 'name_selector': 'source.content.content简历段开头',
 'duty_selector': 'source.content.content简历段现任句',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_api',
 'locator': {'api': {'enabled': True,
                     'method': 'POST',
                     'endpoint': '/queryList',
                     'channel_id_source': '入口页channelsTagSelf.aggChannelIds',
                     'data_path': 'data.results[].source.content.content'}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口页动态栏目编号请求官方接口并解析人物简历现任句。"""
    del html, final_url
    entry_url = str(page_rule.get("url", ""))
    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0", "Referer": entry_url}
    entry_response = session.get(entry_url, headers=headers, timeout=25)
    entry_response.raise_for_status()
    entry_response.encoding = entry_response.apparent_encoding or entry_response.encoding
    channel_match = re.search(r'"aggChannelIds":"(?P<channel_id>\d+)"', entry_response.text)
    if channel_match is None:
        raise RuntimeError("领导介绍入口页缺少聚合栏目编号")
    api_response = session.post(
        "https://yjglt.jiangxi.gov.cn/queryList",
        data=[
            ("channelId[]", channel_match.group("channel_id")),
            ("current", "1"),
            ("pageSize", "999"),
        ],
        headers=headers,
        timeout=25,
    )
    api_response.raise_for_status()
    results = api_response.json().get("data", {}).get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("领导介绍接口 results 字段类型异常")
    parser = str(page_rule["parser"])
    selector_summary = "api:data.results[].source.content.content；简历完整现任句"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"(?P<name>[\u4e00-\u9fa5·]{2,4})[，,].*?(?P<evidence>现任(?P<duty>[^。]+)。)"
    )
    for item in results:
        if not isinstance(item, dict):
            continue
        source = item.get("source", {})
        if not isinstance(source, dict):
            continue
        content_data = source.get("content", {})
        if not isinstance(content_data, dict):
            continue
        content_html = str(content_data.get("content", ""))
        content = re.sub(
            r"\s+",
            " ",
            BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True),
        ).strip()
        match = pattern.search(content)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        if name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "order": len(rows) + 1,
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
