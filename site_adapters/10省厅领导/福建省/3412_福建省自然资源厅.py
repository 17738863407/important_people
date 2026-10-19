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

PAGE_RULE = {'rule_id': '3412',
 'domain': 'zrzyt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_fujian_natural_resources_leader_v1',
 'leader_region_selector': '.ldzc_left a[href]',
 'name_selector': '左侧领导之窗链接文本',
 'duty_selector': '详情页.ldzc_right h3或现任句',
 'detail_link_selector': '.ldzc_left a[href]',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc_left a[href]',
                     'name_selector': '左侧领导之窗链接文本',
                     'duty_selector': '详情页.ldzc_right h3或现任句',
                     'detail_link_selector': '.ldzc_left a[href]',
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


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()


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


def _extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".ldzc_right") or soup
    h3 = region.select_one("h3")
    if h3:
        duty = _clean_text(h3.get_text(" ", strip=True)).rstrip("，,；;。")
        if duty:
            return duty, duty

    text = _clean_text(region.get_text(" ", strip=True))
    pattern = r"现任福建省自然资源厅(.+?)。"
    match = re.search(pattern, text)
    if match:
        duty = "福建省自然资源厅" + match.group(1).strip()
        return duty.rstrip("，,；;。"), match.group(0)
    return "", text[:120]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省自然资源厅领导之窗左侧名单并在线读取详情。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ldzc_left a[href]"):
        raw_name = _clean_text(link.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_name)
        href = link.get("href", "")
        if not name or name == "领导之窗" or name in seen:
            continue
        detail_url = urljoin(base_url, href)
        try:
            detail_html = _fetch_detail_html(detail_url, base_url, html)
        except requests.RequestException:
            continue
        duty, evidence = _extract_duty(detail_html, name)
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
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": ".ldzc_left名单 + 详情.ldzc_right h3/现任句",
            }
        )
    return rows


if __name__ == "__main__":
    main()
