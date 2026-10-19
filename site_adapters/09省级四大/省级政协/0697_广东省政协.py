from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0697',
 'domain': 'www.gdszx.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'custom_guangdong_cppcc_leader_detail_v1',
 'leader_region_selector': 'li.ld_name a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'li.ld_name a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'li.ld_name a[href]',
                     'detail_parser': 'custom_guangdong_cppcc_leader_detail_v1',
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
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.layout.pad20:nth-of-type(4) > '
                                               'div.w710.fr:nth-of-type(4) > div.marT10:nth-of-type(2) > '
                                               'div.ld_des:nth-of-type(2)',
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


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def clean_text(value: str) -> str:
    """规范化页面文本空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def fetch_detail_html(detail_url: str) -> str:
    """读取广东省政协领导详情页。"""
    response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
    response.encoding = "utf-8"
    return response.text


def parse_detail_page(html: str, name: str, detail_url: str, page_rule: dict) -> dict[str, str] | None:
    """从个人简历中的“现任”句抽取职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".ld_des") or soup
    text = clean_text(content.get_text(" ", strip=True))
    match = re.search(r"(?P<sentence>现任(?P<duty>[^。]+)。)", text)
    if not match:
        return None
    duty = match.group("duty").strip()
    if "广东省政协" in duty:
        duty = duty[duty.find("广东省政协"):].strip("，, ")
    return {
        "organization": str(page_rule.get("organization", "")),
        "url": str(page_rule.get("url", "")),
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": match.group("sentence").removeprefix("现任").rstrip("。 "),
        "confidence": "high",
        "parser": str(page_rule.get("parser", "")),
        "selector_summary": "detail=li.ld_name a[href]；content=.ld_des；duty=现任句",
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析广东省政协领导详情页列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    base_url = final_url or str(page_rule.get("url", ""))
    for link in soup.select("li.ld_name a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen_names:
            continue
        detail_url = urljoin(base_url, str(link.get("href", "")))
        output_detail_url = "" if detail_url.rstrip("/") == base_url.rstrip("/") else detail_url
        row = parse_detail_page(fetch_detail_html(detail_url), name, output_detail_url, page_rule)
        if row is None:
            continue
        seen_names.add(name)
        rows.append(row)
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
