from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0944',
 'page_type': '公开接口人物列表页',
 'structure_group': 'CMS领导集体栏目',
 'reuse_scope': 'single_page',
 'load_mode': '静态入口加公开接口',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'page_inline_hebei_academy_cms_api_v2',
 'leader_region_selector': '',
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
                     'max_detail_links': 0},
 'risk_flag': '官网已改为SPA；从公开CMS接口按领导集体栏目ID读取title与summary，内部iurl不作为详情页',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'path': '/api/cms/content/list',
                     'params': {'sid': '411683596922949',
                                'cid': '733394636746821',
                                'pp': 'ee',
                                'pn': 1,
                                'ps': 50,
                                'st': 'createTime#DESC'},
                     'data_path': 'data.rows',
                     'name_field': 'title',
                     'duty_field': 'summary'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}

def compact_text(value: str) -> str:
    """去除姓名内空格，便于识别“刘 波”“程 煜”等格式。"""
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """调用官网公开CMS接口解析河北省科学院领导集体。"""
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    api_rule = dict(dict(page_rule.get("locator") or {}).get("api") or {})
    api_path = str(api_rule.get("path") or "")
    api_params = dict(api_rule.get("params") or {})
    parsed_url = urlsplit(final_url)
    api_url = f"{parsed_url.scheme}://{parsed_url.netloc}{api_path}"
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        api_url,
        params=api_params,
        timeout=30,
        verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"领导集体接口返回异常：{payload.get('msg', '未知错误')}")
    api_rows = payload.get("data", {}).get("rows", [])
    if not isinstance(api_rows, list):
        raise RuntimeError("领导集体接口data.rows不是列表")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；api=/api/cms/content/list；fields=title+summary"

    for item in api_rows:
        if not isinstance(item, dict):
            continue
        name = compact_text(item.get("title", ""))
        duty = " ".join(str(item.get("summary", "") or "").split()).strip("，。；;、 ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
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
