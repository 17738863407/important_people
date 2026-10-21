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

PAGE_RULE = {'rule_id': '1375',
 'domain': 'kjt.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guizhou_science_ldjj_detail_fields_v1',
 'leader_region_selector': '入口页内联导航脚本中的领导之窗链接',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '领导之窗#ldlist脚本中的var src',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '列表页仅姓名，详情页“姓名/职务”字段补职务；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_zdgkc a[href*="/ldjj/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.zfxxgk_zdgkc a[href*="/ldjj/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def fetch_detail_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_detail_fields(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    name_match = re.search(r"姓\s*名\s*[：:]\s*([\u4e00-\u9fff·]{2,5})\s*职\s*务", text)
    duty_match = re.search(r"职\s*务\s*[：:]\s*(.+?)\s*工作分工\s*[：:]", text)
    if not name_match or not duty_match:
        return "", "", ""
    name = name_match.group(1)
    duty = clean_text(duty_match.group(1)).strip(" ：:，,。")
    if not re.search(r"书记|厅长|成员|专员|纪检监察|机关党委|巡视员", duty):
        return "", "", ""
    return name, duty, duty


def extract_leader_index_url(html: str, base_url: str) -> str:
    """优先使用当前领导目录；兼容旧入口中的领导之窗导航。"""
    if BeautifulSoup(html, "html.parser").select_one("#ldlist"):
        return base_url
    match = re.search(r"href=[\"']([^\"']*/ldzc_[^\"']*/)[\"']", html)
    if not match:
        raise RuntimeError("当前入口未发现领导之窗链接")
    return urljoin(base_url, match.group(1))


def extract_detail_urls(html: str, base_url: str) -> list[str]:
    """按领导之窗脚本中的追加顺序提取当前人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#ldlist")
    script = region.select_one("script") if region else None
    script_text = script.string or "" if script else ""
    urls = [
        urljoin(base_url, value)
        for value in re.findall(r"var\s+src\s*=\s*[\"']([^\"']+)[\"']", script_text)
    ]
    if not urls:
        raise RuntimeError("领导之窗未发现当前人物详情链接")
    return list(dict.fromkeys(urls))


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    base_url = str(rule.get("url", "")) or final_url
    leader_index_url = extract_leader_index_url(html, base_url)
    leader_index_html = html if leader_index_url == base_url else fetch_detail_html(leader_index_url)
    detail_urls = extract_detail_urls(leader_index_html, leader_index_url)
    rows = []
    seen = set()
    for detail_url in detail_urls:
        try:
            name, duty, evidence = extract_detail_fields(fetch_detail_html(detail_url))
        except Exception:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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
