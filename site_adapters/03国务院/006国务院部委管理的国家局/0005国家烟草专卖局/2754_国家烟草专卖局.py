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

PAGE_RULE = {'rule_id': '2754',
 'domain': 'www.tobacco.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_tobacco_ldlistcons_cards_v1',
 'leader_region_selector': '.ldlistCons dl',
 'name_selector': 'dd.ld_title',
 'duty_selector': 'dd:not(.ld_title)',
 'detail_link_selector': '.ldlistCons dl a[href]',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.ldlistCons dl',
                     'name_selector': 'dd.ld_title',
                     'duty_selector': 'dd:not(.ld_title)',
                     'detail_link_selector': '.ldlistCons dl a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified_online', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def _join_duty(parts: list[str]) -> str:
    duty = ""
    for part in parts:
        if not part:
            continue
        if not duty:
            duty = part
        elif duty.endswith("国家烟草专卖局") and part.startswith("党组"):
            duty += part
        else:
            duty += "，" + part
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析国家烟草专卖局领导列表卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for card in soup.select(".ldlistCons dl"):
        name_node = card.select_one("dd.ld_title")
        link = card.select_one("a[href]")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty_parts = [_clean_text(node.get_text(" ", strip=True)) for node in card.select("dd:not(.ld_title)")]
        duty = _join_duty(duty_parts)
        detail_url = urljoin(final_url, link.get("href", "").strip()) if link else ""
        if not name or not duty:
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "source_url": final_url,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.ldlistCons dl；name=dd.ld_title；duty=dd:not(.ld_title)；detail=.ldlistCons dl a[href]；api_enabled=False",
            }
        )
    return records


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
