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

PAGE_RULE = {'rule_id': '0627',
 'domain': 'gat.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'guangxi_police_leader_detail_pages_v1',
 'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(3)',
 'name_selector': '.wrap.bg-white a（领导姓名链接）',
 'duty_selector': '详情页正文现任后',
 'detail_link_selector': '.wrap.bg-white a[href*="ldjj_68665"], .wrap.bg-white a[href*="ldhdrl"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap.bg-white:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(".wrap.bg-white a[href]"):
        name = clean_text(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(base_url, href)
        if not (
            re.search(r"/ldjj_68665/t\d+\.shtml(?:$|[?#])", detail_url)
            or "/ldhdrl/index.shtml" in detail_url
        ):
            continue
        if detail_url in seen:
            continue
        links.append((name, detail_url))
        seen.add(detail_url)
    return links


def parse_detail(html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".view, .article, .TRS_Editor")
    evidence = ""
    for block in blocks:
        text = clean_text(block.get_text(" ", strip=True))
        if "现任" in text:
            evidence = text
            break
    if not evidence:
        evidence = clean_text(soup.get_text(" ", strip=True))
    sentence_match = re.search(r"现任[^。]*。", evidence)
    evidence = clean_text(sentence_match.group(0)) if sentence_match else ""
    duty_match = re.search(r"现任(?P<duty>.+?)。", evidence)
    duty = clean_text(duty_match.group("duty")).strip(" ，,。") if duty_match else ""
    duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
    duty = re.sub(r"\s*([、，；：])\s*", r"\1", duty).strip()
    return clean_text(fallback_name), duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_online_html_with_fallback

    base_url = str(page_rule.get("url", ""))
    links = extract_links(html, base_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.wrap.bg-white a领导链接；"
        "name=目录领导链接文本；duty=详情正文现任后；detail=目录领导链接；api_enabled=False"
    )
    for name, detail_url in links:
        try:
            detail_html = fetch_online_html_with_fallback(detail_url, timeout=20).html
        except Exception:
            detail_html = ""
        parsed_name, duty, evidence = parse_detail(detail_html, name)
        if not parsed_name or not duty or parsed_name in seen:
            continue
        seen.add(parsed_name)
        rows.append(
            {
                "name": parsed_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
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
