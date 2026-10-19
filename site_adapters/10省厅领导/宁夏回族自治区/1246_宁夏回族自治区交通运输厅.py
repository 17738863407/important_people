from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '1246',
 'domain': 'jtt.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_ningxia_transport_online_detail_table_v2',
 'leader_region_selector': '.scroll_main a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.scroll_main a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
    for prefix in ("宁夏回族自治区交通运输厅", "自治区交通运输厅"):
        if duty.startswith(prefix):
            duty = duty[len(prefix):]
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty.strip(" ，。")


def load_detail_html(detail_url: str, referer: str) -> str:
    """在线获取领导详情页 HTML。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def extract_profile_from_detail(detail_html: str) -> tuple[str, str, str]:
    """从详情页表格中读取姓名和职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    profile: dict[str, str] = {}
    for row in soup.select("#ofdneed tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = clean_name(cells[-2].get_text(" ", strip=True))
        value = normalize_space(cells[-1].get_text(" ", strip=True))
        if label and value:
            profile[label] = value

    name = clean_name(profile.get("姓名", ""))
    duty = clean_duty(profile.get("职务", ""))
    evidence = duty
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析宁夏回族自治区交通运输厅领导列表，并在线读取详情页补全职务。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=.scroll_main a[href]；detail=online detail page；field=表格“姓名/职务”"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".scroll_main a[href]"):
        listed_name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", listed_name) or listed_name in seen:
            continue
        detail_url = urljoin(page_url, link.get("href", ""))
        detail = urlparse(detail_url)
        source = urlparse(page_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not detail.path.lower().endswith((".html", ".htm"))
        ):
            continue
        detail_name, duty, evidence = extract_profile_from_detail(load_detail_html(detail_url, page_url))
        name = detail_name or listed_name
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
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
