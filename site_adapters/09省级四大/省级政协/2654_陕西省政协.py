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

PAGE_RULE = {'rule_id': '2654',
 'domain': 'www.sxzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_shaanxi_cppcc_category_online_v1',
 'leader_region_selector': '政协领导栏目在线HTML',
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
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': '政协领导栏目在线HTML',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    page_url = final_url or str(page_rule["url"])
    categories = [
        ("主席", "./", "/zxld/zx/"),
        ("副主席", "../fzx/", "/zxld/fzx/"),
        ("秘书长", "../msc/", "/zxld/msc/"),
        ("副秘书长", "../fmsc/", "/zxld/fmsc/"),
    ]
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for duty, relative_path, path_part in categories:
        category_url = urljoin(page_url, relative_path)
        category_html = html
        if relative_path != "./":
            response = requests.get(category_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            category_html = response.text
        soup = BeautifulSoup(category_html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link.get("href") or ""
            name = _normalize_name(link.get_text(" ", strip=True))
            if path_part not in href or not href.endswith(".html") or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                continue
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "organization": page_rule["organization"],
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(category_url, href),
                    "evidence": duty,
                    "parser": "custom_shaanxi_cppcc_category_online_v1",
                    "selector_summary": "政协领导四个在线栏目姓名链接",
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
