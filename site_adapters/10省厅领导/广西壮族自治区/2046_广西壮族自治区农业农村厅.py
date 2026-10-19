from __future__ import annotations

import html as html_lib
import re
import sys
import urllib.request
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2046',
 'domain': 'nynct.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'gx_agriculture_directory_detail_current_sentence_v2',
 'leader_region_selector': 'html > body.bodynei > div.mainbox.bgw:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body.bodynei > div.mainbox.bgw:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_directory_links(html: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*title=[\"'](?P<title>[\u4e00-\u9fff]{2,4})[\"'][^>]*>",
        re.I,
    )
    for match in pattern.finditer(html):
        name = match.group("title")
        href = match.group("href")
        if name in seen or not href.endswith(".shtml"):
            continue
        seen.add(name)
        links.append((name, urljoin(base_url, href)))
    return links


def _extract_duty(detail_html: str, name: str) -> str:
    """只在当前人物简介段落中提取完整“现任……”句。"""
    soup = BeautifulSoup(detail_html or "", "html.parser")
    matches: list[str] = []
    for paragraph in soup.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if name not in re.sub(r"\s+", "", text) or "现任" not in text:
            continue
        matches.extend(re.findall(r"现任[^。]*。", text))
    if len(matches) != 1:
        raise RuntimeError(f"详情现任句命中数量异常：{name}={len(matches)}")
    return matches[0].removeprefix("现任").removesuffix("。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从领导目录进入详情页，抽取正文首句中的现任职务。"""
    from crawler_core.models import PersonRecord

    records: list[object] = []
    for name, detail_url in _extract_directory_links(html, final_url or page_rule["url"]):
        detail_html = _fetch_text(detail_url)
        duty = _extract_duty(detail_html, name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


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
