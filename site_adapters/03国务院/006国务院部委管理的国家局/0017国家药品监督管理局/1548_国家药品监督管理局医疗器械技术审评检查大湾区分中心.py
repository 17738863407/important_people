from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1548',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_mdei_leadership_api_v2',
 'leader_region_selector': 'api:getPageContent.result.content',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'api_config': {'endpoint': '/api/index.php',
                'method': 'GET',
                'params': {'a': 'getPageContent', 'catid': '73'},
                'data_path': 'result.content'},
 'risk_flag': '入口 HTML 仅为 Vue 模板，人物内容由可复现 getPageContent 接口返回',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'api:getPageContent.result.content',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'endpoint': '/api/index.php',
                     'method': 'GET',
                     'params': {'a': 'getPageContent', 'catid': '73'},
                     'data_path': 'result.content'},
             'migration': {'source': 'current_online_api',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_duty(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"党\s+总支", "党总支", text)
    return text.replace(" ", "")


def fetch_content_html(final_url: str, rule: dict) -> str:
    """调用页面自身使用的公开接口，取得当前领导信息正文。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    api_config = dict(rule.get("api_config", {}))
    endpoint = str(api_config.get("endpoint", "/api/index.php"))
    params = dict(api_config.get("params", {}))
    query = "&".join(f"{key}={value}" for key, value in params.items())
    parts = urlsplit(final_url or str(rule.get("url", "")))
    api_url = f"{parts.scheme}://{parts.netloc}{endpoint}?{query}"
    response = fetch_by_raw_requests(api_url)
    payload = json.loads(response.html)
    return str(payload.get("result", {}).get("content", ""))


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    content_html = fetch_content_html(final_url, rule)
    soup = BeautifulSoup(content_html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for paragraph in soup.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff]\s*[\u4e00-\u9fff])\s+(.+)", text)
        if not match:
            continue
        name = match.group(1).replace(" ", "")
        duty = clean_duty(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        if not re.search(r"主任|书记|副书记|委员", duty):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": str(rule.get("organization", "")),
                "url": base_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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
