from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3377',
 'domain': 'zjt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_fujian_housing_department_leader_v1',
 'leader_region_selector': '.ld_list a[href]',
 'name_selector': '.ld_list a title姓名',
 'duty_selector': '详情姓名后个人简历前职务',
 'detail_link_selector': '.ld_list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.zjt-bg:nth-of-type(4) > div.w_1300_2021 > '
                                               'div.erji-container-box > div.ld_con.clearflx:nth-of-type(3)',
                     'name_selector': '.ld_list a title姓名',
                     'duty_selector': '详情姓名后个人简历前职务',
                     'detail_link_selector': '.ld_list a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用在线列表详情链接逐页解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _fetch_detail_html(detail_url: str, referer: str, current_html: str) -> str:
    """在线读取领导详情页。"""
    if detail_url.rstrip("/") == referer.rstrip("/"):
        return current_html
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _parse_detail(name: str, detail_html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    title_node = soup.select_one(".ld_tu p")
    text = re.sub(r"\s+", " ", title_node.get_text(" ", strip=True) if title_node else "")
    spaced_name = r"\s*".join(map(re.escape, name))
    match = re.search(rf"{spaced_name}\s+(.+)$", text)
    return re.sub(r"\s+", "", match.group(1)).rstrip("，,；;。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省住房和城乡建设厅省厅领导页并在线读取详情。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".ld_list a[href]"):
        name = re.sub(r"[\s\u3000]+", "", link.get("title") or link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        if name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            detail_html = _fetch_detail_html(detail_url, base_url, html)
        except requests.RequestException:
            continue
        duty = _parse_detail(name, detail_html)
        if not duty:
            continue
        seen.add(name)
        output_detail_url = detail_url
        if output_detail_url.rstrip("/") == base_url.rstrip("/"):
            output_detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": output_detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".ld_list名单+详情姓名后职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()
