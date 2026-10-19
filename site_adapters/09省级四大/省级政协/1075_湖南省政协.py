from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1075',
 'domain': 'www.hunanzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_hunan_cppcc_panel_dl_v1',
 'leader_region_selector': '.container.zxld .panel dl',
 'name_selector': 'strong a',
 'duty_selector': 'span',
 'detail_link_selector': 'strong a',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.container.zxld .panel dl',
                     'name_selector': 'strong a',
                     'duty_selector': 'span',
                     'detail_link_selector': 'strong a',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '政协领导列表在在线页面DOM中完整呈现'},
             'migration': {'source': 'legacy_online_adapter',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split()).strip()


def compact_person_name(text: str) -> str:
    return re.sub(r"\s+", "", text)


def normalize_duty(raw: str, name: str) -> str:
    text = clean_text(raw)
    compact_text = re.sub(r"\s+", "", text)
    compact_name = compact_person_name(name)
    if compact_text.startswith(compact_name):
        return compact_text[len(compact_name):]
    return text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for item in soup.select(".container.zxld .panel dl"):
        name_link = item.select_one("strong a")
        duty_node = item.select_one("span")
        name = compact_person_name(clean_text(name_link.get_text(" ", strip=True))) if name_link else ""
        duty = normalize_duty(duty_node.get_text(" ", strip=True), name) if duty_node else ""
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        source_url = str(page_rule.get("url", ""))
        href = str(name_link.get("href", "")) if name_link else ""
        detail_url = urljoin(final_url or source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": ".container.zxld .panel dl strong+span",
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
