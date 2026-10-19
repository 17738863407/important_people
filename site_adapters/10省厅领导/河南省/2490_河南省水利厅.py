from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2490',
 'domain': 'slt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'custom_henan_water_top_leader_list_v1',
 'leader_region_selector': '.colLeft',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.colLeft',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    text = re.sub(r"（.*?）|\\(.*?\\)", "", text)
    return _clean_text(text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析河南省水利厅顶部领导交替列表。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    source_url = str(page_rule.get("url", final_url))
    detail_urls: dict[str, str] = {}
    for link in soup.select(".colLeft a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        href = link.get("href", "").strip()
        if 2 <= len(name) <= 4 and href:
            detail_url = urldefrag(urljoin(final_url or source_url, href)).url
            parsed = urlsplit(detail_url)
            if parsed.scheme in {"http", "https"} and parsed.netloc and detail_url.rstrip("/") != source_url.rstrip("/"):
                detail_urls[name] = detail_url

    region = soup.select_one(".colLeft")
    if not region:
        return []
    values = [_clean_text(text) for text in region.stripped_strings]
    values = [value for value in values if value and value != "水利厅领导"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    index = 0
    while index + 1 < len(values):
        duty = values[index]
        name = _clean_name(values[index + 1])
        index += 2
        if not name or not duty or name in seen:
            continue
        if not re.search(r"厅长|党组|纪检监察组", duty):
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_urls.get(name, ""),
                "evidence": duty,
                "parser": "custom_henan_water_top_leader_list_v1",
                "selector_summary": ".colLeft；职务/姓名交替列表",
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
