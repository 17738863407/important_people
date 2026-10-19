from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2337',
 'domain': 'sft.sc.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'html > body > div.content.tldmain:nth-of-type(2)',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.content.tldmain:nth-of-type(2)',
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


def clean_text(text: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"[\s\u00A0\u3000]+", " ", str(text or "")).strip()


def clean_name(text: str) -> str:
    """清理姓名中的空白。"""
    return re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip()


def load_detail_html(detail_url: str) -> str:
    """在线读取当前人物详情页。"""
    response = requests.get(
        detail_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_duty_from_detail(detail_html: str) -> tuple[str, str]:
    """从详情页“现任”句抽取职务。"""
    text = clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    if not match:
        return "", text[:160]
    duty = re.sub(r"[\s\u00A0\u3000]+", "", match.group(0)[2:-1]).strip(" ：:，,。；;")
    if duty.startswith("四川省司法厅"):
        duty = duty[len("四川省司法厅"):].strip(" ：:，,。；;")
    evidence = re.sub(r"^现任\s*", "", match.group(0)).removesuffix("。").strip()
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析四川省司法厅领导详情链，避免通用详情解析返回空结果。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    region = soup.select_one("html > body > div.content.tldmain:nth-of-type(2)") or soup.select_one("div.tldmain") or soup
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in {"简历", "分工"} or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url or source_url, link.get("href", ""))
        detail_html = load_detail_html(detail_url)
        duty, evidence = extract_duty_from_detail(detail_html)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_sichuan_justice_detail_v1",
                "selector_summary": "div.content.tldmain a[href]；detail_text=现任句",
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
