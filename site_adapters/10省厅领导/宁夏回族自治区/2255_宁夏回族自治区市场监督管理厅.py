from __future__ import annotations

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

PAGE_RULE = {'rule_id': '2255',
 'domain': 'scjg.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ningxia_market_supervision_leader_window_v1',
 'leader_region_selector': 'html > body.body_bg > div.container:nth-of-type(4) > div.pageMain > '
                           'div.ldzc_pagemain.clearfix',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body.body_bg > div.container:nth-of-type(4) > div.pageMain > '
                                               'div.ldzc_pagemain.clearfix',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '领导之窗正文块直接包含姓名和职务，需排除分工长文本'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'fixed',
                           'behavior_changed': True}}}


def _make_record(page_rule: dict, name: str, duty: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url="",
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def _extract_duty(profile_text: str, name: str) -> str:
    """从人物首段简介分号后的原始任职句提取职务。"""
    current_match = re.search(r"现任[^。]*。", profile_text)
    if current_match:
        return current_match.group(0).removeprefix("现任").strip().removesuffix("。").rstrip()
    duty_match = re.search(r"[；;](?P<duty>[^。]+。)", profile_text)
    if duty_match:
        return duty_match.group("duty").strip().removesuffix("。").rstrip()
    name_prefix = re.escape(name) + r"[，,：:]?"
    fallback_match = re.search(name_prefix + r"(?P<duty>[^。]+。)", profile_text)
    return fallback_match.group("duty").strip().removesuffix("。").rstrip() if fallback_match else ""


def _fetch_online_html(url: str) -> str:
    """以官网可接受的简洁请求头在线重取领导页面。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析宁夏市场监督管理厅领导之窗正文块，保留首段职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(
        "html > body.body_bg > div.container:nth-of-type(4) > div.pageMain > div.ldzc_pagemain.clearfix"
    )
    if region is None:
        soup = BeautifulSoup(_fetch_online_html(page_rule["url"]), "html.parser")
        region = soup.select_one(
            "html > body.body_bg > div.container:nth-of-type(4) > div.pageMain > div.ldzc_pagemain.clearfix"
        )
    if region is None:
        return []
    records: list[object] = []
    for item in region.select("div.jg-list-left-1 > ul"):
        title_node = item.select_one("div.jg-list-title")
        profile_node = item.select_one("div.jg-list-text")
        if title_node is None or profile_node is None:
            continue
        title_text = re.sub(r"\s+", "", title_node.get_text(" ", strip=True))
        name = title_text.replace("【详情】", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        profile_text = ""
        for paragraph in profile_node.select("p"):
            candidate = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", paragraph.get_text("", strip=True))
            if name in candidate and "。" in candidate:
                profile_text = candidate
                break
        duty = _extract_duty(profile_text, name)
        if not name or not duty:
            continue
        record = _make_record(page_rule, name, duty)
        link_node = title_node.select_one("a[href]")
        if link_node is not None and "详情" in link_node.get_text("", strip=True):
            record.detail_url = urljoin(page_rule["url"], str(link_node.get("href") or ""))
        records.append(record)
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
