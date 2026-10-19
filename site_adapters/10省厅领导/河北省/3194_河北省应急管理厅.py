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

PAGE_RULE = {'rule_id': '3194',
 'domain': 'yjgl.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'api_json_html',
 'parser': 'hebei_emergency_management_api_ldxx_v1',
 'leader_region_selector': '接口content中的人物信息段落',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'api+css',
 'locator': {'css': {'leader_region_selector': '接口content中的人物信息段落',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True,
                     'url': 'https://yjgl.hebei.gov.cn/portal/infopublic/getPortalNewsList',
                     'method': 'POST',
                     'params': {'id': 'ldxx'},
                     'reason': '领导成员内容由稳定接口返回；请求必须携带浏览器UA、AJAX与来源页请求头'},
             'migration': {'source': 'last_batch_online_template',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从在线渲染正文或领导信息接口动态提取姓名和职务。"""
    parser = str(page_rule["parser"])
    selector_summary = "POST接口getPortalNewsList(id=ldxx)的content段落；姓名后以党委开头的完整职务句"
    response = requests.post(
        "https://yjgl.hebei.gov.cn/portal/infopublic/getPortalNewsList",
        data={"id": "ldxx"},
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://yjgl.hebei.gov.cn",
            "Referer": "https://yjgl.hebei.gov.cn/portal/infopublic/toInfoPublic?selectedId=jgzn",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    api_content = str(response.json().get("content") or "")
    candidates = BeautifulSoup(api_content, "html.parser").find_all("p")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in candidates:
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        match = re.match(
            r"^(?P<name>(?:[\u4e00-\u9fff·]\s*){2,4}?)(?P<duty>党委[^。]*)$",
            text,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = match.group("duty").strip("，,。 ").replace("（兼）", "").replace("(兼)", "")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
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
