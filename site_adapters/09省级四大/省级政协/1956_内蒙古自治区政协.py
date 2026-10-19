from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1956',
 'domain': 'www.nmgzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'raw_http',
 'parser': 'custom_nmgzx_leader_query_links_v1',
 'leader_region_selector': '.container-content a[href*="cppccLeader/publicPage.html"]',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.container-content a[href*="cppccLeader/publicPage.html"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'reason': '入口页index.js在线请求/jsondata/mhNav.json，使用data[id=2].list[].data字段'},
             'migration': {}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    page_url = final_url or str(page_rule["url"])
    data_url = urljoin(page_url, "../../jsondata/mhNav.json")
    response = requests.get(data_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = json.loads(response.content.decode("utf-8-sig"))
    rows: list[dict] = []
    seen_names: set[str] = set()
    leader_root = next((item for item in payload.get("data", []) if str(item.get("id")) == "2"), {})
    for group in leader_root.get("list", []):
        duty = clean_text(group.get("name", "")).replace(" ", "")
        for person in group.get("data", []):
            name = clean_text(person.get("name", "")).replace(" ", "")
            href = str(person.get("url", ""))
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append({
                "name": name,
                "duty": duty,
                "detail_url": urljoin(page_url, href),
                "evidence": duty,
                "selector_summary": "data[id=2].list[].name/data[].name/url；人物链接query含title+name",
            })
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
