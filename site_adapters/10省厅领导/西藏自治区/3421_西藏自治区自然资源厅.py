from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3421',
 'domain': 'zrzyt.xizang.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_online_detail_tibet_natural_resources_leader_v1',
 'leader_region_selector': '领导之窗姓名详情链接',
 'name_selector': '链接文本',
 'duty_selector': '详情页正文首段截断分工',
 'detail_link_selector': 'a[href*="t20"]',
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
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '领导之窗姓名详情链接',
                     'name_selector': '链接文本',
                     'duty_selector': '详情页正文首段截断分工',
                     'detail_link_selector': 'a[href*="t20"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5]) (?=[\u4e00-\u9fa5])", "", text)


def _extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".view, .TRS_UEDITOR")
    if content:
        text = _clean_text(content.get_text(" ", strip=True))
    else:
        text = _clean_text(soup.get_text(" ", strip=True))
        marker = f"下属单位 > {name}"
        if marker in text:
            text = text.split(marker, 1)[1]
        elif name in text:
            text = text.split(name, 1)[-1]
    text = text.lstrip("：:，,。 ")
    duty = re.split(r"[，,]\s*(?:负责|主持|协助|分管)|[。；;]\s*(?:负责|主持|协助|分管)", text, maxsplit=1)[0]
    duty = duty.strip("：:，,。；; ")
    return duty, text[:120]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析西藏自治区自然资源厅领导之窗在线详情。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="t20"]'):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,5}", name) or name in seen:
            continue
        href = link.get("href", "")
        detail_url = urljoin(base_url, href)
        try:
            response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            continue
        duty, evidence = _extract_duty(response.text, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": "领导之窗详情链接 + 详情正文职务",
            }
        )
    return rows


if __name__ == "__main__":
    main()
