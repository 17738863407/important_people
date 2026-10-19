from __future__ import annotations

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

PAGE_RULE = {'rule_id': '0637',
 'domain': 'gat.nx.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'ningxia_police_leader_detail_pages_v1',
 'leader_region_selector': '.zfxxgk_zdgkc ul li',
 'name_selector': '.zfxxgk_zdgkc ul li a',
 'duty_selector': '详情页 #vsb_content_503 .view 文本中“现任”后内容',
 'detail_link_selector': '.zfxxgk_zdgkc ul li a',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.zfxxgk_zdgkc ul li a',
                     'detail_parser': 'ningxia_police_detail_present_duty_v1',
                     'detail_name_selector': '目录页链接文本',
                     'detail_duty_selector': '详情页 #vsb_content_503 .view 文本中“现任”后内容',
                     'detail_content_selector': '#vsb_content_503 .view',
                     'max_detail_links': 50},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_zdgkc ul li',
                     'name_selector': '.zfxxgk_zdgkc ul li a',
                     'duty_selector': '详情页 #vsb_content_503 .view 文本中“现任”后内容',
                     'detail_link_selector': '.zfxxgk_zdgkc ul li a',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def is_chinese_name(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", clean_text(value)))


def extract_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".zfxxgk_zdgkc ul li a[href]"):
        name = clean_text(anchor.get_text(" ", strip=True))
        if not is_chinese_name(name):
            continue
        detail_url = urljoin(base_url, str(anchor.get("href") or ""))
        detail = urlparse(detail_url)
        source = urlparse(base_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or "/ldxx/" not in detail.path
            or not detail.path.lower().endswith((".html", ".htm"))
            or detail_url in seen
        ):
            continue
        seen.add(detail_url)
        links.append((name, detail_url))
    return links


def parse_detail_page(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    content = soup.select_one("#vsb_content_503 .view") or soup.select_one("#vsb_content_503") or soup
    page_text = clean_text(content.get_text(" ", strip=True))
    duty = ""
    duty_match = re.search(r"现任(?P<duty>.+?)[。；;]", page_text)
    if duty_match:
        duty = clean_text(duty_match.group("duty")).strip(" ：:，,。；;")
        duty = re.sub(r"^职务\s*[：:]\s*", "", duty)
    evidence_match = re.search(r"现任[^。]*。", page_text)
    evidence = duty if evidence_match or duty else ""
    return clean_text(fallback_name), duty, evidence


def fetch_detail_html(detail_url: str, timeout: int = 20) -> str:
    session = requests.Session()
    session.trust_env = False
    response = session.get(
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


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    organization = str(page_rule.get("organization", ""))
    base_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.zfxxgk_zdgkc ul li；"
        "name=.zfxxgk_zdgkc ul li a；duty=详情页#vsb_content_503 .view现任后；"
        "detail=.zfxxgk_zdgkc ul li a；api_enabled=False"
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
            "organization": organization,
            "url": base_url,
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

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.models import PersonRecord
    page_rule = apply_business_source(PAGE_RULE)
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        str(page_rule["url"]),
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    raw_rows = parse_page(response.text, response.url, page_rule)
    records = [
        PersonRecord(
            organization=str(row.get("organization", "")),
            url=str(row.get("url", "")),
            name=str(row.get("name", "")),
            duty=str(row.get("duty", "")),
            detail_url=str(row.get("detail_url", "")),
            evidence=str(row.get("evidence", "")),
            confidence=str(page_rule.get("confidence", "high")),
            parser=str(row.get("parser", "")),
            selector_summary=str(row.get("selector_summary", "")),
            script_sequence=str(page_rule["rule_id"]),
        )
        for row in raw_rows
    ]
    if not records:
        raise RuntimeError("在线直连获取成功，但原目录与详情解析结果为空")
    output_name = f"{Path(__file__).stem}.txt"
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, records)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
