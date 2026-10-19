from __future__ import annotations

import re
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


PAGE_RULE = {'rule_id': '0629',
 'domain': 'gat.hlj.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 '_fetch_mode_override': True,
 'extract_mode': 'list_direct',
 'parser': 'heilongjiang_police_api_v1',
 'leader_region_selector': 'common/search API results',
 'name_selector': 'title',
 'duty_selector': 'content中的完整现任句',
 'detail_link_selector': 'url',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'api_result_url'},
 'risk_flag': '入口HTML含验证码表单文字会触发公共异常页误判，已核验raw_http及公开API',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'common/search API results',
                     'name_selector': 'title',
                     'duty_selector': 'content中的完整现任句',
                     'detail_link_selector': 'url',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.zfxx-right'],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'channel_url': '/common/getChannelList?channelCode=c115792&websiteCodeName=gat',
                     'search_url': '/common/search/{channel_id}',
                     'data_path': 'data.results'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    import requests

    base_url = str(page_rule.get("url", ""))
    headers = {"Referer": base_url, "User-Agent": "Mozilla/5.0"}
    channel_url = urljoin(base_url, "/common/getChannelList?channelCode=c115792&websiteCodeName=gat")
    channel_response = requests.get(channel_url, headers=headers, timeout=30)
    channel_response.raise_for_status()
    channel_id = str(channel_response.json().get("results", {}).get("channelId") or "")
    if not channel_id:
        return []
    search_url = urljoin(base_url, f"/common/search/{channel_id}")
    search_response = requests.get(
        search_url,
        params={
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "50",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        headers=headers,
        timeout=30,
    )
    search_response.raise_for_status()
    results = search_response.json().get("data", {}).get("results", [])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in results:
        name = clean_text(str(item.get("title") or ""))
        detail_text = clean_text(BeautifulSoup(str(item.get("content") or ""), "html.parser").get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        evidence = clean_text(evidence_match.group(0)) if evidence_match else ""
        duty = evidence.removeprefix("现任").removesuffix("。")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url or base_url, str(item.get("url") or "")),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "common/getChannelList+common/search API；name=title；evidence=content现任句；detail=url",
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
