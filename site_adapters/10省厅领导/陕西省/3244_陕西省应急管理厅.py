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

PAGE_RULE = {'rule_id': '3244',
 'domain': 'yjt.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_shaanxi_emergency_leader_v1',
 'leader_region_selector': '.w-leader-cont-left .submenu a[href]',
 'name_selector': '.w-name',
 'duty_selector': '.w-posi:last-of-type',
 'detail_link_selector': '.w-leader-cont-left .submenu a[href]',
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
 'locator': {'css': {'leader_region_selector': 'html > body > div.w-content-bg:nth-of-type(1) > div.wrap.main-box > '
                                               'div.w-leaderInfo.f-pb30',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def detail_row(detail_html: str, fallback_name: str, detail_url: str, page_rule: dict) -> dict[str, str] | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".w-name")
    name = re.sub(r"\s+", "", name_node.get_text("", strip=True) if name_node else fallback_name)
    duties = []
    for duty_node in soup.select(".w-posi"):
        duty = duty_node.get_text("；", strip=True)
        duty = re.sub(r"\s+", "", duty)
        duty = re.sub(r"；+", "；", duty).strip("；")
        if duty:
            duties.append(duty)
    if not duties:
        for match in re.finditer(r"document\.write\('<p class=\"w-posi[^\"]*\">(.*?)</p>'\)", detail_html, re.S):
            duty = match.group(1)
            duty = re.sub(r"<br\s*/?>|&lt;br\s*/?&gt;", "；", duty, flags=re.I)
            duty = re.sub(r"<.*?>", "", duty)
            duty = re.sub(r"\s+", "", duty)
            duty = duty.replace("党委委员陕西省消防", "党委委员；陕西省消防")
            duty = re.sub(r"；+", "；", duty).strip("；")
            if duty:
                duties.append(duty)
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duties:
        return None
    duty = duties[-1].replace("（兼）", "").replace("(兼)", "")
    return {
        "name": name,
        "duty": "",
        "detail_url": detail_url,
        "evidence": duty,
        "parser": page_rule["parser"],
        "selector_summary": "左侧领导链接 + 在线详情页最后一个.w-posi",
    }


def resolve_leader_navigation(html: str, final_url: str) -> tuple[str, str]:
    """入口页使用 meta refresh 时，在线取得承载领导子菜单的首位详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".w-leader-cont-left .submenu a[href]"):
        return html, final_url
    for meta in soup.select("meta[http-equiv][content]"):
        if str(meta.get("http-equiv") or "").lower() != "refresh":
            continue
        match = re.search(r"\burl\s*=\s*(?P<target>.+)$", str(meta.get("content") or ""), re.I)
        if not match:
            continue
        target_url = urljoin(final_url, match.group("target").strip(" '\""))
        try:
            response = requests.get(target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            return html, final_url
        if response.encoding and response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = "utf-8"
        return response.text, response.url
    return html, final_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析陕西省应急管理厅在线领导详情。"""
    from bs4 import BeautifulSoup

    html, navigation_url = resolve_leader_navigation(html, final_url)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".w-leader-cont-left .submenu a[href]"):
        name = re.sub(r"\s+", "", link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(navigation_url, link.get("href", ""))
        try:
            response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue
        if response.encoding and response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = "utf-8"
        row = detail_row(response.text, name, detail_url, page_rule)
        if row:
            seen.add(row["name"])
            row["order"] = str(len(rows) + 1)
            rows.append(row)
    return rows


if __name__ == "__main__":
    main()
