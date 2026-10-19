from __future__ import annotations

import html as html_lib
import re
import sys
import urllib.request
from urllib.parse import urljoin
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2050',
 'domain': 'nynct.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ningxia_agriculture_leader_detail_title_v1',
 'leader_region_selector': 'html > body > div.zwxxgk_bd:nth-of-type(1)',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.zwxxgk_bd:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return _clean_text(text)


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"<a\b[^>]*href=[\"'](?P<href>[^\"']*?/nmtld/[^\"']+)[\"'][^>]*>(?P<body>.*?)</a>", re.I | re.S)
    for match in pattern.finditer(html):
        name = re.sub(r"\s+", "", _html_to_text(match.group("body")))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or name in seen:
            continue
        seen.add(name)
        links.append((name, urljoin(base_url, match.group("href"))))
    return links


def _extract_duty(detail_text: str, name: str) -> str:
    spaced_name = r"\s*".join(map(re.escape, name))
    match = re.search(rf"领导\s+{spaced_name}\s+(.*?)\s+日期", detail_text)
    if not match:
        return ""
    return _clean_text(match.group(1))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """进入厅领导详情页，从标题区抽取职务。"""
    from crawler_core.models import PersonRecord

    records: list[object] = []
    for name, detail_url in _extract_leader_links(html, final_url or page_rule["url"]):
        try:
            detail_text = _html_to_text(_fetch_text(detail_url))
        except Exception:
            continue
        duty = _extract_duty(detail_text, name)
        if not duty:
            continue
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
