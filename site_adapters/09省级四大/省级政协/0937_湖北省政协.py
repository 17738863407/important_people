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

PAGE_RULE = {'rule_id': '0937',
 'domain': 'www.hbzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hubei_cppcc_grouped_leaders_v1',
 'leader_region_selector': 'body',
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
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def normalize_token(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", ""))


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    detail_urls = {}
    for link in soup.select("a[href]"):
        name = normalize_token(link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·•]{2,8}", name):
            detail_urls.setdefault(name, urljoin(base_url, link.get("href", "")))

    lines = [clean_text(line) for line in soup.get_text("\n", strip=True).splitlines() if clean_text(line)]
    rows = []
    seen = set()
    current_duty = ""
    in_leader_block = False

    for line in lines:
        token = normalize_token(line)
        if token == "政协领导":
            in_leader_block = True
            current_duty = ""
            continue
        if in_leader_block and token in {"党派团体", "版权所有：中国人民政治协商会议湖北省委员会"}:
            break
        if not in_leader_block:
            continue
        if token in {"主席", "主\u3000席"}:
            current_duty = "主席"
            continue
        if token == "副主席":
            current_duty = "副主席"
            continue
        if token == "秘书长":
            current_duty = "秘书长"
            continue
        if current_duty not in {"主席", "副主席", "秘书长"}:
            continue
        name = token
        if not re.fullmatch(r"[\u4e00-\u9fff·•]{2,8}", name):
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
