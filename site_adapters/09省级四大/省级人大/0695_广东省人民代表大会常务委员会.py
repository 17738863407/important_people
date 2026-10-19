from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def extract_resume_current_sentence(detail_html: str) -> str:
    """仅在人物详情页的“简历”正文内提取“现任……。”完整句。"""
    import re

    from bs4 import BeautifulSoup

    detail_soup = BeautifulSoup(detail_html, "html.parser")
    for resume_region in detail_soup.select("div.gdscwhcy-introduce"):
        title_node = resume_region.select_one("div.introduce-title")
        if clean_text(title_node.get_text(" ", strip=True)) != "简历" if title_node else True:
            continue
        content_node = resume_region.select_one("div.introduce-content")
        resume_text = clean_text(content_node.get_text(" ", strip=True)) if content_node else ""
        match = re.search(r"现任.*?。", resume_text)
        if match:
            return clean_text(match.group(0)).removeprefix("现任").rstrip("。")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表顺序解析成员，并在线进入详情页提取简历中的现任句。"""
    import re

    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = final_url or str(page_rule.get("url", ""))
    seen: set[str] = set()

    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for item in soup.select("ul.gl_list li"):
            link = item.select_one("a[href]")
            name = clean_text(link.get_text(" ", strip=True)) if link else ""
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            href = str(link.get("href") or "")
            detail_url = urljoin(source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
            if detail_url.rstrip("/") == source_url.rstrip("/"):
                detail_url = ""

            evidence = ""
            if detail_url:
                try:
                    response = session.get(detail_url, timeout=30)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding or response.encoding
                    detail_url = str(response.url)
                    evidence = extract_resume_current_sentence(response.text)
                except requests.RequestException:
                    evidence = ""

            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": "",
                    "detail_url": detail_url,
                    "evidence": evidence,
                    "confidence": "high" if evidence else "medium",
                    "parser": "page_detail_guangdong_people_congress_resume_current_v1",
                }
            )
    return rows


PAGE_RULE = {'rule_id': '0695',
 'domain': 'www.gdpc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_detail_guangdong_people_congress_resume_current_v1',
 'leader_region_selector': 'ul.gl_list li',
 'name_selector': 'ul.gl_list li > a[href]',
 'duty_selector': 'div.gdscwhcy-introduce中标题为“简历”的div.introduce-content内现任.*?。',
 'detail_link_selector': 'ul.gl_list li > a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail_online',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'ul.gl_list li > a[href]',
                     'detail_parser': 'page_detail_guangdong_people_congress_resume_current_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '现任.*?。',
                     'detail_content_selector': 'div.gdscwhcy-introduce > div.introduce-content',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '逐一在线进入列表人物详情页，仅在“简历”正文范围提取现任完整句',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.gl_list li',
                     'name_selector': 'ul.gl_list li > a[href]',
                     'duty_selector': 'div.gdscwhcy-introduce中标题为“简历”的div.introduce-content内现任.*?。',
                     'detail_link_selector': 'ul.gl_list li > a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


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
