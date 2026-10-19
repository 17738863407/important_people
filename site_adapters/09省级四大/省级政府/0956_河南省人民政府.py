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

PAGE_RULE = {'rule_id': '0956',
 'domain': 'www.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_gov_grouped_leaders_v1',
 'leader_region_selector': '.zwxxgk_bd',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zwxxgk_bd',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\u200b", "")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", "").replace("\u200b", "")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zwxxgk_bd") or soup
    base_url = final_url or str(rule.get("url", ""))
    detail_urls = {}
    for link in region.select("a[href]"):
        name = normalize_name(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        detail_url = urljoin(base_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        if detail_url and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            detail_urls.setdefault(name, detail_url)

    lines = [clean_text(line) for line in region.get_text("\n", strip=True).splitlines() if clean_text(line)]
    rows = []
    seen = set()
    in_block = False
    current_duty = ""

    for line in lines:
        token = normalize_name(line)
        if token == "省政府领导":
            in_block = True
            current_duty = ""
            continue
        if in_block and token.startswith("河南省人大常委会"):
            break
        if not in_block:
            continue
        direct = re.fullmatch(r"省长[：:](?P<name>[\u4e00-\u9fff\s\u3000\u200b·]{2,8})", line)
        if direct:
            name = normalize_name(direct.group("name"))
            duty = "省长"
        elif token == "副省长":
            current_duty = "副省长"
            continue
        elif token == "秘书长":
            current_duty = "秘书长"
            continue
        elif current_duty in {"副省长", "秘书长"} and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", token):
            name = token
            duty = current_duty
        else:
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_urls.get(name, ""),
                "evidence": duty,
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
