from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2956',
 'domain': 'wlt.nmg.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V009_text_profile_paragraph_v1',
 'leader_region_selector': 'div#barrierfree_container',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#barrierfree_container',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)
    text = re.sub(r"\s+([，。、；：（）])", r"\1", text)
    text = re.sub(r"（\s+", "（", text)
    text = re.sub(r"([，、])\s+", r"\1", text)
    return text


def extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".article") or soup.select_one("#zoom") or soup
    text = clean_text(region.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    if match:
        raw_evidence = clean_text(match.group(0))
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            raw_evidence,
        ).strip()
        duty = clean_text(raw_evidence.removeprefix("现任")).rstrip("。")
        return duty, evidence
    pattern = rf"内蒙古自治区文化和旅游厅(.+?){re.escape(name)}[，,](?:男|女)"
    match = re.search(pattern, text)
    if match:
        duty = clean_text(match.group(1)).rstrip("。")
        return duty, duty
    return "", ""


def load_url(url: str) -> str:
    """在线读取实时人物详情页。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析内蒙古自治区文化和旅游厅领导简介列表及详情。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        href = link.get("href", "")
        if not re.search(r"t\d+_\d+\.html$", href):
            continue
        detail_url = urljoin(page_rule["url"], href)
        try:
            duty, evidence = extract_duty(load_url(detail_url), name)
        except Exception:
            duty, evidence = "", ""
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "page_inline_nmg_wlt_leader_detail_v1",
                "selector_summary": "list=a[href$=.html]；detail=.article；pattern=现任/厅职务姓名",
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
