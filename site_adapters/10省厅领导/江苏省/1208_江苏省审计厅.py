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



PAGE_RULE = {'rule_id': '1208',
 'domain': 'jssjt.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_jiangsu_audit_local_detail_xianren_v1',
 'leader_region_selector': '.scroll_main1 a[href]',
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
 'locator': {'css': {'leader_region_selector': '.scroll_main1 a[href]',
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


def clean_evidence(value: str) -> str:
    """清理人物详情中的现任句式标签和句末标点。"""
    text = re.sub(r"^(?:现任|职务|现任职务)[：:]?", "", normalize_space(value)).rstrip("。")
    return re.sub(r"，(?:分管|主持|负责|协管).*$", "", text)


def extract_duty_from_detail(detail_html: str, name: str) -> tuple[str, str]:
    """从详情页“现任……”句提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    lines = [normalize_space(line) for line in soup.get_text("\n", strip=True).splitlines()]
    for line in lines:
        if name not in clean_name(line) or "现任" not in line:
            continue
        match = re.search(r"现任(.+?)(?:，(?:分管|主持|负责|协管)|。|$)", line)
        if not match:
            continue
        sentence_match = re.search(r"现任[^。]*。", line)
        evidence = sentence_match.group(0) if sentence_match else f"现任{match.group(1).rstrip('。')}。"
        return normalize_space(match.group(1)).rstrip("。"), clean_evidence(evidence)
    return "", ""


def is_real_detail_url(detail_url: str, page_url: str) -> bool:
    """仅接受同站真实独立人物文章页。"""
    detail = urlparse(detail_url)
    source = urlparse(page_url)
    return bool(
        detail.scheme in {"http", "https"}
        and detail.netloc.lower() == source.netloc.lower()
        and not detail.fragment
        and re.search(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html$", detail.path)
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江苏省审计厅领导分工列表，并在线读取详情页补全职务。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = (
        "strategy=custom_parse_page；selector=.scroll_main1 a[href]；"
        "detail=online_detail；field=text contains 现任"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".scroll_main1 a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(page_url, link.get("href", ""))
        if not is_real_detail_url(detail_url, page_url):
            continue
        response = requests.get(
            detail_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": page_url,
            },
            timeout=30,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_html = response.text
        duty, evidence_text = extract_duty_from_detail(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence_text,
                "parser": parser,
                "selector_summary": selector_summary,
            }
        )
    return rows


def main(output_dir: Path | None = None) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.exporter import export_records
    from crawler_core.business_sources import apply_business_source
    from crawler_core.models import PersonRecord
    from crawler_core.naming import build_output_name
    from playwright.sync_api import sync_playwright

    page_rule = apply_business_source(PAGE_RULE)
    raw_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(str(page_rule["url"]), wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        soup = BeautifulSoup(page.content(), "html.parser")
        for link in soup.select(".scroll_main1 a[href]"):
            name = clean_name(link.get_text(" ", strip=True))
            if name in seen or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
                continue
            detail_url = urljoin(page.url, link.get("href", ""))
            if not is_real_detail_url(detail_url, str(page_rule["url"])):
                continue
            page.goto(detail_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1200)
            duty, evidence_text = extract_duty_from_detail(page.content(), name)
            if not duty:
                continue
            seen.add(name)
            raw_rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")),
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": evidence_text,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "strategy=chrome_cdp；list=.scroll_main1 a[href]；detail=现任句取职务",
                }
            )
        page.close()

    records = [
        PersonRecord(
            organization=str(row.get("organization", page_rule["organization"])),
            url=str(row.get("url", page_rule["url"])),
            name=str(row.get("name", "")),
            duty=str(row.get("duty", "")),
            detail_url=str(row.get("detail_url", "")),
            evidence=str(row.get("evidence", "")),
            confidence=str(page_rule.get("confidence", "high")),
            parser=str(row.get("parser", page_rule["parser"])),
            
            selector_summary=str(row.get("selector_summary", "")),
            script_sequence=str(page_rule["rule_id"]),
        )
        for row in raw_rows
    ]
    if not records:
        raise RuntimeError("在线 CDP 获取成功，但解析结果为空")

    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(page_rule["rule_id"], page_rule["organization"])
    export_records(output_path, records)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

