from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1224',
 'domain': 'jt.jiangxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态JSON列表加详情页',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'extract_mode': 'api_to_detail',
 'collector': 'custom_api_http',
 'parser': 'custom_jiangxi_transport_json_details_v2',
 'leader_region_selector': 'api:/jxsjtyst/jgld/jgld-articleList.json',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_online',
                     'detail_collector_type': 'requests',
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_api',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_main td.info a',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'endpoint_path': '/jxsjtyst/jgld/jgld-articleList.json',
                     'method': 'GET',
                     'name_field': 'title',
                     'detail_url_field': 'urls.pc'},
             'migration': {'source': 'last_batch_online_template+manual_detail_refine',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def load_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    for tag in soup.find_all(["p", "div", "span"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if text and "工作分工" not in text and len(text) <= 80:
            text = re.sub(rf"^{re.escape(name)}\s*", "", text)
            if any(word in text for word in ("书记", "厅长", "巡视员", "局长")):
                return text
    text = clean_text(soup.get_text(" ", strip=True))
    work_index = text.find("工作分工")
    if work_index < 0:
        return ""
    before_work = text[:work_index]
    name_matches = list(re.finditer(re.escape(name), before_work))
    if not name_matches:
        return ""
    duty = before_work[name_matches[-1].end():]
    duty = re.sub(r"来源：.*$", "", duty).strip()
    return clean_text(duty)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按官方JSON列表顺序请求人物详情页并提取现任职务。"""
    del html, final_url
    source_url = str(page_rule.get("url") or "")
    api_config = dict(page_rule.get("locator", {}).get("api", {}))
    article_list_url = urljoin(source_url, str(api_config["endpoint_path"]))
    session = requests.Session()
    session.trust_env = False
    list_response = session.get(article_list_url, timeout=30)
    list_response.raise_for_status()
    items = list_response.json()
    if not isinstance(items, list) or not items:
        raise RuntimeError("官方领导JSON列表为空")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("官方领导JSON存在非对象记录")
        name = clean_text(str(item.get("title") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            raise RuntimeError(f"官方领导JSON姓名异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"官方领导JSON姓名重复：{name}")
        urls = json.loads(str(item.get("urls") or "{}"))
        detail_url = urljoin(source_url, str(urls.get("pc") or ""))
        detail_response = session.get(detail_url, timeout=30)
        detail_response.raise_for_status()
        detail_response.encoding = detail_response.apparent_encoding or "utf-8"
        duty = load_detail_duty(detail_response.text, name)
        if not duty:
            raise RuntimeError(f"人物详情页缺少可验证现任职务：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "jgld-articleList.json姓名及顺序+官方详情页现任职务",
            }
        )
    if len(rows) != len(items):
        raise RuntimeError(f"官方领导记录数量未完整对账：{len(rows)}/{len(items)}")
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
