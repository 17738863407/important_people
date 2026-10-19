from __future__ import annotations

import html
import re
import sys
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

PAGE_RULE = {'rule_id': '0941',
 'domain': 'hct.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'V009_text_profile_paragraph_v1',
 'leader_region_selector': 'html > body > div.autoContainer.clearfix:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_link_selector': 'html > body > div.autoContainer.clearfix:nth-of-type(3) .columnList.pull-right ul.newsList a[href]',
                     'detail_parser': 'detail_meta_description_content_prefix_v1',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.autoContainer.clearfix:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面直接提供领导列表及详情信息'}}}


def clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_meta(source: str, name: str) -> str:
    pattern = rf'<meta\s+[^>]*name=["\']{re.escape(name)}["\'][^>]*content=(["\'])(.*?)\1'
    match = re.search(pattern, source, flags=re.I | re.S)
    return clean_text(match.group(2)) if match else ""


def extract_leader_links(list_html: str, base_url: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', list_html, flags=re.I | re.S):
        url = urljoin(base_url, html.unescape(match.group(1)).strip())
        text = clean_text(match.group(2))
        parsed = urlparse(url)
        key = (text, url)
        if (
            re.fullmatch(r'[\u4e00-\u9fa5·]{2,4}', text)
            and parsed.hostname == 'hct.henan.gov.cn'
            and re.fullmatch(r'/\d{4}/\d{2}-\d{2}/\d+\.html', parsed.path)
            and key not in seen
        ):
            seen.add(key)
            rows.append(key)
    return rows


def extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    description = extract_meta(detail_html, "Description")
    content_match = re.search(r'<div\s+class=["\']content["\'][^>]*>(.*?)<p\s+class=["\']operator["\']', detail_html, flags=re.I | re.S)
    content_text = clean_text(content_match.group(1)) if content_match else ""
    evidence = description or content_text
    search_text = evidence
    if not search_text:
        return "", ""
    prefix = search_text.split(name, 1)[0].strip(" ，,。；;：:")
    if not prefix and name in content_text:
        prefix = content_text.split(name, 1)[0].strip(" ，,。；;：:")
        evidence = content_text
    return prefix, evidence


def parse_page(html_source: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html_source, "html.parser")
    region = soup.select_one("html > body > div.autoContainer.clearfix:nth-of-type(3)")
    if not region:
        return []
    leader_list = region.select_one(".columnList.pull-right ul.newsList")
    if not leader_list:
        return []
    rows: list[dict] = []
    for name, detail_url in extract_leader_links(str(leader_list), final_url):
        try:
            response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or response.encoding
        detail_html = response.text
        duty, evidence = extract_duty(detail_html, name)
        if not duty:
            continue
        rows.append({
            "name": name,
            "duty": "",
            "order": len(rows) + 1,
            "detail_url": detail_url,
            "evidence": duty,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "html > body > div.autoContainer.clearfix:nth-of-type(3) .columnList.pull-right ul.newsList a[href] + detail meta Description/content",
        })
    return rows


def main() -> None:
    """在线解析领导列表和详情页。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
