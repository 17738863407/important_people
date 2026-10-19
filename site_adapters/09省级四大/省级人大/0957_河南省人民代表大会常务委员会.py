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

PAGE_RULE = {'rule_id': '0957',
 'domain': 'www.henanrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_renda_grouped_leaders_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
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
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '本地 HTML 已包含主任之窗分组名单，使用页面级解析'},
             'migration': {'source': 'sequential_static_html_builder',
                         'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", "")).strip()


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    detail_urls = {}
    for link in soup.select("a[href]"):
        name = normalize_name(link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            detail_urls.setdefault(name, urljoin(base_url, link.get("href", "")))

    lines = [clean_text(line) for line in soup.get_text("\n", strip=True).splitlines() if clean_text(line)]
    rows = []
    seen = set()
    in_block = False
    current_duty = ""

    for line in lines:
        token = normalize_name(line)
        if token == "主任之窗":
            in_block = True
            current_duty = ""
            continue
        if in_block and token.startswith("[常委会委员]"):
            break
        if not in_block:
            continue
        direct = re.fullmatch(r"主任[：:](?P<name>[\u4e00-\u9fff\s\u3000·]{2,8})", line)
        if direct:
            name = normalize_name(direct.group("name"))
            duty = "主任"
        elif token in {"主任：", "主任:"}:
            current_duty = "主任"
            continue
        elif token in {"副主任：", "副主任:"}:
            current_duty = "副主任"
            continue
        elif token in {"秘书长：", "秘书长:"}:
            current_duty = "秘书长"
            continue
        elif current_duty in {"主任", "副主任", "秘书长"} and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", token):
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
                "organization": str(rule.get("organization", "")),
                "url": base_url,
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
