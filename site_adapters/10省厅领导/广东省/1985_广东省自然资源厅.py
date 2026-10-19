from __future__ import annotations

import html as html_lib
import re
import sys
from urllib.request import Request, urlopen
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1985',
 'domain': 'nr.gd.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'guangdong_natural_resources_leader_detail_v1',
 'leader_region_selector': '.aside.left .asideList a[href]',
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
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.aside.left .asideList a[href]',
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


def _clean_text(text: str) -> str:
    text = html_lib.unescape(text).replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return _clean_text(text)


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析广东省自然资源厅领导详情页。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule["url"])
    if not soup.select_one(".aside.left .asideList a[href]"):
        soup = BeautifulSoup(_fetch_text(source_url), "html.parser")
    records = []
    seen_urls: set[str] = set()
    for link in soup.select(".aside.left .asideList a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url or source_url, str(link.get("href") or ""))
        if not name or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        output_detail_url = "" if detail_url.rstrip("/") == source_url.rstrip("/") else detail_url
        detail_text = _html_to_text(_fetch_text(detail_url))
        duty_match = re.search(r"现任[^。]*。", detail_text)
        if not duty_match:
            continue
        evidence = _clean_text(duty_match.group(0)).removeprefix("现任").rstrip().removesuffix("。").rstrip()
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=source_url,
                name=name,
                duty="",
                detail_url=output_detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".aside.left .asideList领导导航 + 详情页现任句",
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
