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

PAGE_RULE = {'rule_id': '0705',
 'domain': 'www.ggj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_ggj_leader_detail_v1',
 'leader_region_selector': 'a[href] script',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'list_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href] script',
                     'detail_parser': 'page_inline_ggj_leader_detail_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '列表页姓名由showTitle脚本输出，职务需进入详情页基本信息句补齐',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.mainbox.boxcenter:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页和详情页静态 HTML 已包含完整领导信息'},
             'migration': {'source': 'sequential_manual_detail_fix',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def iter_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """从列表页 showTitle 脚本中提取姓名和详情页链接。"""
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        match = re.search(r"showTitle\(['\"](?P<name>[^'\"]+)['\"]\)", str(link))
        if not match:
            continue
        name = clean_text(match.group("name"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        if name in seen:
            continue
        seen.add(name)
        links.append((name, detail_url))
    return links


def extract_duty_from_detail(name: str, detail_html: str) -> tuple[str, str]:
    """从详情页“姓名，职务，男/女...”基本信息句中抽取职务。"""
    text = clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
    pattern = rf"{re.escape(name)}[，,](?P<duty>.*?)[，,](?:男|女)[，,]"
    match = re.search(pattern, text)
    if not match:
        return "", text[:300]
    duty = re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", clean_text(match.group("duty")))
    current_sentence = re.search(r"现任[^。]*。", text)
    if current_sentence:
        return duty, clean_text(current_sentence.group(0))
    evidence_start = max(0, match.start() - 30)
    evidence_end = min(len(text), match.end() + 120)
    return duty, text[evidence_start:evidence_end]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析国家机关事务管理局领导列表及详情页基本信息。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    base_url = final_url
    rows: list[dict[str, str]] = []
    for name, detail_url in iter_leader_links(html, base_url):
        detail_result = fetch_by_raw_requests(detail_url)
        duty, detail_evidence = extract_duty_from_detail(name, detail_result.html)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "列表页a[href]内showTitle取姓名；详情页基本信息句取职务",
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
