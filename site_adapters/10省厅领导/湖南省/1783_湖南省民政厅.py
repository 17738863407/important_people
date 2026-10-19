from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1783',
 'domain': 'mzt.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'hunan_mzt_leader_detail_v1',
 'leader_region_selector': '.table_list tbody tr a[title]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.container:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用原 CSS/HTML 定位解析'}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace(",", "，")).strip()


def _clean_standalone_concurrent_marker(text: str) -> str:
    """删除独立“兼”状态标记，保留具体第二职务。"""
    return re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", _clean_text(text)).strip()


def _fetch_detail_html(url: str) -> str:
    fetch_url = url.replace("https://mzt.hunan.gov.cn/", "http://mzt.hunan.gov.cn/", 1)
    request = Request(fetch_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        body = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return body.decode(encoding, errors="replace")


def _extract_duty(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(".jdld_leader_zw")
    if not node:
        return ""
    for span in node.select("span"):
        span.decompose()
    return _clean_standalone_concurrent_marker(node.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析湖南省民政厅机构领导列表，并从详情页抽取职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()

    for link in soup.select(".table_list tbody tr a[title]"):
        name = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue

        detail_url = urljoin(page_rule["url"], link.get("href", ""))
        parsed_detail = urlparse(detail_url)
        if (
            parsed_detail.netloc.lower() != urlparse(str(page_rule["url"])).netloc.lower()
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        if not detail_url:
            continue
        duty = _extract_duty(_fetch_detail_html(detail_url))
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
                selector_summary="list=.table_list a[title]; detail=.jdld_leader_zw",
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
