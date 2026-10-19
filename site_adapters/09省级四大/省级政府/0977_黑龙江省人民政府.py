from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0977',
 'domain': 'www.hlj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_heilongjiang_gov_szfld_group_v1',
 'leader_region_selector': '.szfld',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.szfld a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 'locator': {'css': {'leader_region_selector': '.szfld',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.szfld a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '本地 HTML 省政府领导容器已包含分组名单，使用页面级解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", "")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".szfld")
    if not region:
        return []
    base_url = final_url or str(rule.get("url", ""))
    detail_urls = {}
    for link in region.select("a[href]"):
        name = normalize_name(link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            detail_urls.setdefault(name, urljoin(base_url, link.get("href", "")))

    lines = [clean_text(line) for line in region.get_text("\n", strip=True).splitlines() if clean_text(line)]
    rows = []
    seen = set()
    current_duty = ""
    for line in lines:
        token = normalize_name(line)
        if token in {"省政府领导", "更多+"}:
            continue
        if token == "省长":
            current_duty = "省长"
            continue
        if token == "副省长":
            current_duty = "副省长"
            continue
        if token == "秘书长":
            current_duty = "秘书长"
            continue
        if current_duty not in {"省长", "副省长", "秘书长"}:
            continue
        name = token
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        key = (name, current_duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "organization": str(rule.get("organization", "")),
                "url": base_url,
                "name": name,
                "duty": current_duty,
                "detail_url": detail_urls.get(name, ""),
                "evidence": current_duty,
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
