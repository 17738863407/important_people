from __future__ import annotations

import html as html_lib
import re
import sys
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

PAGE_RULE = {'rule_id': '2218',
 'domain': 'rst.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'hunan_hrss_list_detail_titles_v1',
 'leader_region_selector': '.xxgkzd-box li a',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'list_to_detail'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.xxgkmain:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页给出姓名链接，职务由在线详情页字段确认'}}}


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text)
    return text.strip()


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析湖南省人社厅机构领导列表，并补入详情页职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen: set[str] = set()
    for link in soup.select(".xxgkzd-box li a[href]"):
        name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        parsed_detail = urlparse(detail_url)
        if (
            parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or not parsed_detail.path.lower().endswith((".shtml", ".html", ".htm"))
        ):
            continue
        fetch_url = detail_url.replace("https://rst.hunan.gov.cn/", "http://rst.hunan.gov.cn/", 1)
        try:
            request = Request(fetch_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                detail_html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            continue
        detail_text = _clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
        match = re.search(r"职\s*务\s*[:：]\s*(.+?)\s*(?:工作分工|个人简介)\s*[:：]", detail_text)
        duty = match.group(1).strip(" ：:，,。.；;") if match else ""
        if not duty:
            continue
        seen.add(name)
        records.append(_make_record(page_rule, name, duty, detail_url))
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
