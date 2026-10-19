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

PAGE_RULE = {'rule_id': '0935',
 'domain': 'www.hbrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hebei_renda_grouped_members_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a.title[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '只抽取主任、副主任和秘书长，遇到委员标题后停止，不追加末尾委员人物版块',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a.title[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线 DOM 包含分组名单，按网页职务标题分组解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def heading_key(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", "").replace("\u3000", ""))


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    detail_urls = {}
    for link in soup.select("a.title[href]"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href", ""))
        detail_url = urljoin(base_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url and detail_url.rstrip("/") != base_url.rstrip("/"):
            detail_urls.setdefault(name, detail_url)
    lines = [clean_text(line) for line in soup.get_text("\n", strip=True).splitlines() if clean_text(line)]
    rows = []
    seen = set()
    current_duty = ""
    current_evidence = ""

    for line in lines:
        key = heading_key(line)
        heading_match = re.fullmatch(r"(主任|副主任|秘书长)[：:]", key)
        if heading_match:
            current_duty = heading_match.group(1)
            current_evidence = current_duty
            continue
        if re.fullmatch(r"委员[：:]", key):
            break
        if not current_duty:
            continue
        name = line.replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        key_pair = (name, current_duty)
        if key_pair in seen:
            continue
        seen.add(key_pair)
        rows.append(
            {
                "name": name,
                "duty": current_duty,
                "detail_url": detail_urls.get(name, ""),
                "evidence": current_evidence,
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
