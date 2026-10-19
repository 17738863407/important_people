from __future__ import annotations

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

PAGE_RULE = {'rule_id': '1599',
 'domain': 'www.moa.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'moa_leader_list_online_detail_duties_v2',
 'leader_region_selector': 'html > body > div.c_cont_com2.c_over:nth-of-type(5) > div.c_p_padd:nth-of-type(1) > '
                           'div.c_leadermod.c_fl:nth-of-type(1)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'list_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': ".c_leadermod .c_ldm_list a[href*='/jg/leaders/']",
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.c_cont_com2.c_over:nth-of-type(5) > '
                                               'div.c_p_padd:nth-of-type(1) > div.c_leadermod.c_fl:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析农业农村部部领导列表，并从实时详情页基本信息句提取职务。"""
    import re

    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".c_leadermod .c_ldm_list a[href*='/jg/leaders/']"):
        name = "".join(link.get_text(" ", strip=True).split())
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or "")) if final_url else ""
        if not detail_url:
            continue
        detail_result = fetch_by_raw_requests(detail_url)
        detail_text = " ".join(BeautifulSoup(detail_result.html, "html.parser").get_text(" ", strip=True).split())
        match = re.search(rf"{re.escape(name)}[，,](?P<duty>.*?)[，,](?:男|女)[，,]", detail_text)
        if not match:
            continue
        duty = " ".join(match.group("duty").split())
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "moa_leader_list_online_detail_duties_v2",
                "selector_summary": "leader=.c_leadermod .c_ldm_list a[href*='/jg/leaders/']; duty=详情页姓名，职务，男/女正则",
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
