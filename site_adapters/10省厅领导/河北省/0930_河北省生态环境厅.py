from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0930',
 'domain': 'hbepb.hebei.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_inline_hebei_ecology_leader_detail_links_v1',
 'leader_region_selector': 'html > body > div.all_box:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则遍历导航区详情链接，误抓整页正文和环境监察专员；改为仅解析当前厅领导信息栏目姓名链接',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.all_box:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录页提供当前领导详情链接，详情页 h1/h2 直出姓名职务'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'behavior_changed': True}}}


NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5]{2,3}$")


def clean_text(value: str) -> str:
    """压缩姓名、职务和证据文本中的连续空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def fetch_detail_html(url: str) -> str:
    """请求当前领导详情页 HTML。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_detail(name: str, detail_url: str) -> tuple[str, str]:
    """从详情页标题区提取职务。"""
    soup = BeautifulSoup(fetch_detail_html(detail_url), "html.parser")
    scope = soup.select_one("div.p_nei") or soup
    title = clean_text((scope.select_one("h1") or scope.find("h1") or "").get_text(" ", strip=True))
    duty = clean_text((scope.select_one("h2.reply") or scope.find("h2") or "").get_text(" ", strip=True))
    if title and title != name:
        return "", ""
    if not duty:
        return "", ""
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河北省生态环境厅当前厅领导信息目录及其详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；selector=a[href*=tinglingdaoxinxi]；detail=h1+h2.reply"

    for link in soup.select("a[href*='tinglingdaoxinxi']"):
        name = clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not NAME_PATTERN.match(name) or name in seen or not href.endswith(".html"):
            continue
        detail_url = urljoin(page_url, href)
        duty, evidence = extract_detail(name, detail_url)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
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
