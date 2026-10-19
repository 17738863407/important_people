from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '0624',
 'domain': 'gat.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'fujian_police_leader_detail_pages_v1',
 'leader_region_selector': '.leader_area',
 'name_selector': '.leader_area a[href*="/ldjs/"]；详情页简介段段首姓名',
 'duty_selector': '.leader_area p（现任后）',
 'detail_link_selector': '.leader_area a[href*="/zwgk/jggk/ldjs/"]',
 'content_scope': {'start_anchor': '更多领导',
                   'end_anchor': '',
                   'include_selectors': ['.leader_area'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'custom_parse_page_fetch_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.leader_area a[href*="/zwgk/jggk/ldjs/"]',
                     'detail_parser': 'fujian_police_leader_detail_pages_v1',
                     'detail_name_selector': '.leader_area h1/.leader_area p',
                     'detail_duty_selector': '.leader_area p（现任后）',
                     'detail_content_selector': '.leader_area',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader_area',
                     'name_selector': '.leader_area a[href*="/ldjs/"]；详情页简介段段首姓名',
                     'duty_selector': '.leader_area p（现任后）',
                     'detail_link_selector': '.leader_area a[href*="/zwgk/jggk/ldjs/"]',
                     'content_scope': {'start_anchor': '更多领导',
                                       'end_anchor': '',
                                       'include_selectors': ['.leader_area'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导信息为在线静态详情页 HTML，不是 JSON 接口'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if "/zwgk/jggk/ldjs/" not in href:
            continue
        name = clean_text(anchor.get_text(" ", strip=True))
        url = urljoin(base_url, href)
        if name and url not in seen:
            links.append((name, url))
            seen.add(url)
    return links


def parse_detail(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one(".leader_area") or soup
    for paragraph in area.find_all("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "现任" not in text:
            continue
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fa5·]{2,4})[，,]", text)
        duty_match = re.search(r"现任(?P<duty>.+?)[。；;]", text)
        if duty_match:
            name = clean_text(name_match.group("name")) if name_match else clean_text(fallback_name)
            duty = clean_text(duty_match.group("duty")).strip(" ，,。")
            sentence_match = re.search(r"现任[^。]*。", text)
            evidence = clean_text(sentence_match.group(0)) if sentence_match else duty
            return name, duty, evidence
    return clean_text(fallback_name), "", clean_text(area.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_online_html_with_fallback

    base_url = str(page_rule.get("url", ""))
    links = extract_links(html, base_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.leader_area；"
        "name=更多领导链接/详情简介段首姓名；duty=详情简介现任后；"
        "detail=.leader_area a[href*=ldjs]；api_enabled=False"
    )
    for fallback_name, detail_url in links:
        detail_html = html if detail_url.rstrip("/") == base_url.rstrip("/") else ""
        if not detail_html:
            try:
                detail_html = fetch_online_html_with_fallback(detail_url, timeout=20).html
            except Exception:
                detail_html = ""
        name, duty, evidence = parse_detail(detail_html, fallback_name)
        if not name or not duty or name in seen:
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
                "parser": str(page_rule.get("parser", "")),
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
