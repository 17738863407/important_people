from __future__ import annotations

import html as html_lib
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

PAGE_RULE = {'rule_id': '2012',
 'domain': 'www.nxzx.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ningxia_cppcc_leader_detail_titles_v1',
 'leader_region_selector': '政协领导详情页标题职务',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '政协领导详情页标题职务',
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
    text = html_lib.unescape(text).replace("\u3000", " ").replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    text = re.sub(r"<!--[\s\S]*?-->", " ", html)
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return _clean_text(text)


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析宁夏回族自治区政协领导详情页标题职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url or str(page_rule["url"])
    records = []
    seen_names: set[str] = set()
    for link in soup.select('a[href]'):
        name = _clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen_names:
            continue
        raw_href = str(link.get("href", ""))
        absolute_match = re.search(r"https?://[^\s\"'<>]+\.html", raw_href)
        detail_url = absolute_match.group(0) if absolute_match else urljoin(page_url, raw_href.strip())
        if "/zxgk/zxld/" not in detail_url or detail_url.rstrip("/") == page_url.rstrip("/"):
            continue
        detail_soup = BeautifulSoup(_fetch_text(detail_url), "html.parser")
        duty_candidates = []
        for node in detail_soup.select(".xxqg7 p"):
            candidate = _clean_text(node.get_text(" ", strip=True))
            if "政协" in candidate and re.search(r"主席|秘书长", candidate):
                duty_candidates.append(candidate)
        duty = min(duty_candidates, key=len) if duty_candidates else ""
        duty = duty.removesuffix("。").strip()
        if not duty:
            continue
        seen_names.add(name)
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
                selector_summary="入口a[href]动态详情链；详情.xxqg7 p标题职务",
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
