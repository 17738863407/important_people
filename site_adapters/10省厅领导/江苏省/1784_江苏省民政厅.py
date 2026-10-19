from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1784',
 'domain': 'mzt.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_jiangsu_mzt_sidebar_leaders_v1',
 'leader_region_selector': '.column-left .column-col a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.column-left .column-col a',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线侧栏领导信息含职务和姓名'}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def split_duty_name(text: str) -> tuple[str, str]:
    text = clean_text(text)
    compound_match = re.search(r"([\u4e00-\u9fa5]{2,6}[·•][\u4e00-\u9fa5]{2,6})$", text)
    if compound_match:
        name = compound_match.group(1).replace("•", "·")
        duty = clean_text(text[: compound_match.start()])
        return duty, name
    match = re.search(r"([\u4e00-\u9fa5]{2,4})$", text)
    if not match:
        return "", ""
    name = match.group(1)
    duty = clean_text(text[: match.start()])
    return duty, name


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    base_url = str(page_rule.get("url", "")) or final_url
    source = urlparse(base_url)
    seen: set[str] = set()
    for link in soup.select(".column-left .column-col a[href]"):
        title = clean_text(link.get_text(" ", strip=True))
        duty, name = split_duty_name(title)
        normal_name = re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name)
        compound_name = re.fullmatch(r"[\u4e00-\u9fa5]{2,6}·[\u4e00-\u9fa5]{2,6}", name)
        if not duty or not (normal_name or compound_name) or name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        detail = urlparse(detail_url)
        if (
            detail.scheme not in {"http", "https"}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip("/") == source.path.rstrip("/")
            or not (
                re.search(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html$", detail.path)
                or re.search(r"/col/col\d+(?:/index\.html)?/?$", detail.path)
            )
        ):
            detail_url = ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "侧栏领导信息链接末尾姓名拆分",
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
