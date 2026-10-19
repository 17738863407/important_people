from __future__ import annotations

import sys
import re
from pathlib import Path

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3242',
 'domain': 'yjt.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_api_online_qinghai_emergency_leader_v1',
 'leader_region_selector': '/orgController.do?getAllPersonnel',
 'name_selector': 'f_real_name',
 'duty_selector': 'f_weixin + f_qq',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#index > div.current.w:nth-of-type(2) > '
                                               'div.page.leader:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '在线 POST getAllPersonnel 返回结构化领导数据'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析青海省应急管理厅官方人员接口。"""
    api_url = "http://yjt.qinghai.gov.cn/orgController.do?getAllPersonnel"
    response = requests.post(api_url, headers={"User-Agent": "Mozilla/5.0", "Referer": page_rule["url"]}, timeout=20)
    response.raise_for_status()
    data = response.json()
    organization = page_rule["organization"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for person in data[0].get("1", []):
        name = re.sub(r"\s+", "", person.get("f_real_name") or "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        user_id = str(person.get("f_user_id") or "").strip()
        org_id = str(person.get("f_org_id") or "").strip()
        detail_url = (
            f"http://yjt.qinghai.gov.cn/Mobile/jggk_ldxx.html?userId={user_id}&orgId={org_id}"
            if user_id.isdigit() and org_id.isdigit()
            else ""
        )
        evidence = "；".join(
            value for value in [str(person.get("f_weixin") or "").strip(), str(person.get("f_qq") or "").strip()] if value
        )
        duty = evidence
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": "官方接口getAllPersonnel f_real_name/f_weixin/f_qq",
            }
        )
    return rows


if __name__ == "__main__":
    main()
