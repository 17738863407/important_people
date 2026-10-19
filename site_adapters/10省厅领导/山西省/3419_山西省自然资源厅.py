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

PAGE_RULE = {'rule_id': '3419',
 'domain': 'zrzyt.shanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_detail_online_shanxi_natural_resources_leader_v1',
 'leader_region_selector': '领导之窗姓名链接',
 'name_selector': '链接文本',
 'duty_selector': '详情正文首个职务段',
 'detail_link_selector': 'a[href*=ldjj]',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '领导之窗姓名链接',
                     'name_selector': '链接文本',
                     'duty_selector': '详情正文首个职务段',
                     'detail_link_selector': 'a[href*=ldjj]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()


def _extract_duty(detail_html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(detail_html, "html.parser")
    profile = soup.select_one(".leaderWarp .kyy_textR.scy_ldzcxl")
    if profile:
        parts = [_clean_text(p.get_text(" ", strip=True)) for p in profile.select("p")]
        parts = [part.rstrip("，,；;。") for part in parts if part]
        if len(parts) >= 2:
            return parts[1], parts[1]

    for para in soup.select(".trs_editor_view p"):
        text = _clean_text(para.get_text(" ", strip=True)).rstrip("，,；;。")
        if not text or len(text) > 80:
            continue
        if re.search(r"(厅|党组|纪检监察组|巡视员|地质勘查局|林业和草原局|绿化委员会)", text):
            return text, text
    return "", _clean_text(soup.get_text(" ", strip=True))[:120]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析山西省自然资源厅政务公开页领导之窗在线详情。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a[href*=ldjj]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        href = link.get("href", "")
        detail_url = urljoin(base_url, href)
        try:
            response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue
        if response.encoding and response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = "utf-8"
        duty, evidence = _extract_duty(response.text)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": "政务公开领导之窗链接 + 详情正文职务段",
                "order": str(len(rows) + 1),
            }
        )
    return rows


if __name__ == "__main__":
    main()
