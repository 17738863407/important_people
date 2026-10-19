from __future__ import annotations

import sys
import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2830',
 'domain': 'tyjrt.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_ningxia_veterans_left_detail_v1',
 'leader_region_selector': 'div.ldzc-content',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'div.ldzc-content',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _fetch_online_html(url: str) -> str:
    """以官网可接受的简洁请求头在线读取页面。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _detail_evidence(detail_url: str) -> str:
    """在线读取人物详情页中的完整现任职务句。"""
    soup = BeautifulSoup(_fetch_online_html(detail_url), "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"现任宁夏回族自治区退役军人事务厅[^。]*。", text)
    return re.sub(r"^现任", "", _clean_text(match.group(0))).rstrip("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.ldzc-content")
    if region is None:
        soup = BeautifulSoup(_fetch_online_html(page_rule["url"]), "html.parser")
        region = soup.select_one("div.ldzc-content")
    if region is None:
        return []
    rows: list[dict] = []
    leader_group = None
    for group in region.select("li.er-active"):
        heading = group.find("div", recursive=False)
        if heading is not None and _clean_text(heading.get_text(" ", strip=True)) == "领导之窗":
            leader_group = group
            break
    if leader_group is None:
        return []
    for link in leader_group.select("li.link > a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        detail_url = urljoin(page_rule["url"], link["href"])
        evidence = _detail_evidence(detail_url)
        if not evidence:
            continue
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_ningxia_veterans_left_detail_v1",
                "selector_summary": "左侧领导链接+详情现任职务句",
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
