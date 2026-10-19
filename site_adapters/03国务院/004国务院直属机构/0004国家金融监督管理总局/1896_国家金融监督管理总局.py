from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from urllib import request as urllib_request


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1896',
 'domain': 'www.nfra.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'raw_http',
 'parser': 'custom_nfra_leader_api_v2',
 'leader_region_selector': '/cn/static/data/leaderinfo/list/data_orgid=1.json',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'api',
 'locator': {'css': {'leader_region_selector': '/cn/static/data/leaderinfo/list/data_orgid=1.json',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '新机构概况页通过 /leaderinfo/list 接口加载总局领导数据'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def normalize_duty(text: str) -> str:
    text = clean_text(text)
    if re.fullmatch(r"[\u4e00-\u9fa5](?:\s+[\u4e00-\u9fa5])+", text):
        return text.replace(" ", "")
    return text


def fetch_json(url: str, referer: str) -> dict:
    """请求 JSON 接口。"""
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
        },
    )
    with urllib_request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    rows: list[dict] = []
    seen_names: set[str] = set()
    page_url = str(page_rule.get("url", ""))
    api_urls = [
        "https://www.nfra.gov.cn/cn/static/data/leaderinfo/list/data_orgid=1.json",
        "https://www.nfra.gov.cn/cbircweb/leaderinfo/list?orgid=1",
    ]
    data: dict = {}
    for api_url in api_urls:
        try:
            data = fetch_json(api_url, page_url)
            break
        except Exception:
            continue
    leader_items = ((data.get("data") or {}).get("leaderinfo") or []) if isinstance(data, dict) else []
    for item in sorted(leader_items, key=lambda value: int(value.get("orderNo") or 9999)):
        name = clean_text(str(item.get("leaderName") or "")).replace(" ", "").replace("\u3000", "")
        duty = normalize_duty(str(item.get("leaderFulltitle") or item.get("leaderShorttitle") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "api=/cn/static/data/leaderinfo/list/data_orgid=1.json；fields=leaderName+leaderFulltitle",
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
