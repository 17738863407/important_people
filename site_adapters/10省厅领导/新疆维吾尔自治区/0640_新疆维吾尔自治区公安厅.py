from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0640',
 'domain': 'gat.xinjiang.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'xinjiang_police_leader_detail_pages_v1',
 'leader_region_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
 'name_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
 'duty_selector': '详情页 .conTxt 文本中“现任”后内容',
 'detail_link_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_parse_page_fetch_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
                     'detail_parser': 'xinjiang_police_detail_present_duty_v1',
                     'detail_name_selector': '目录页链接文本',
                     'detail_duty_selector': '详情页 .conTxt 文本中“现任”后内容',
                     'detail_content_selector': '.conTxt',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
                     'name_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
                     'duty_selector': '详情页 .conTxt 文本中“现任”后内容',
                     'detail_link_selector': '.zfxxgk_container a[href*="/gat/ldxx/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def extract_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('.zfxxgk_container a[href*="/gat/ldxx/"]'):
        href = str(anchor.get("href") or "")
        name = clean_text(anchor.get_text(" ", strip=True))
        if "/ldxx1/" in href or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen:
            continue
        seen.add(detail_url)
        links.append((name, detail_url))
    return links


def fetch_detail_html(detail_url: str, timeout: int = 20) -> str:
    response = requests.get(
        detail_url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def parse_detail_page(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    content = soup.select_one(".conTxt") or soup.select_one("#leftbox") or soup
    text = clean_text(content.get_text(" ", strip=True))
    duty = ""
    duty_match = re.search(r"现任(?P<duty>.+?)[。；;]", text)
    if duty_match:
        duty = clean_text(duty_match.group("duty")).strip(" ，,。；;")
    evidence = duty
    return clean_text(fallback_name), duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.zfxxgk_container a[href*=gat/ldxx/]；"
        "name=.zfxxgk_container a[href*=gat/ldxx/]；duty=详情页.conTxt现任后；"
        "detail=.zfxxgk_container a[href*=gat/ldxx/]；api_enabled=False"
    )
    for fallback_name, detail_url in extract_leader_links(html, base_url):
        try:
            detail_html = fetch_detail_html(detail_url, timeout=20)
        except Exception:
            detail_html = ""
        name, duty, evidence = parse_detail_page(detail_html, fallback_name)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": evidence,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
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
