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

PAGE_RULE = {'rule_id': '1964',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'nanning_commerce_leader_profile_v2',
 'leader_region_selector': '.trs_editor_view p',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': "a[href^='./t'][href$='.html']",
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': "a[href^='./t'][href$='.html']",
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 1},
 'risk_flag': '领导班子索引指向按日期更新的单篇正文，应动态选择当前文章并限制正文边界',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.trs_editor_view p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href^='./t'][href$='.html']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'current_online_index_and_article',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(text: str) -> str:
    """压缩排版空白，并清理中文标点两侧空格。"""
    value = re.sub(r"[\s\u3000\u00a0\u2000-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([：:，、；])\s*", r"\1", value)


def _fetch_current_article(index_html: str, base_url: str) -> tuple[str, str]:
    """从领导班子目录动态取得当前正文页。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(index_html, "html.parser")
    link = soup.select_one("a[href^='./t'][href$='.html']")
    if link is None:
        raise RuntimeError("领导班子目录未找到当前正文链接")
    article_url = urljoin(base_url, str(link.get("href") or ""))
    result = fetch_by_raw_requests(article_url)
    return result.html, result.final_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析目录指向的当前领导班子简介正文。"""
    from crawler_core.models import PersonRecord

    article_html, _article_url = _fetch_current_article(html, final_url or page_rule["url"])
    soup = BeautifulSoup(article_html, "html.parser")
    records = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".trs_editor_view p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·\s]{2,8})(?:（女）)?[：:](?P<duty>.+)", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty")).rstrip("。；; ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names or not duty:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="index=current /ldbz/t*.html; scope=.trs_editor_view p; pattern=name:duty",
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
