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

PAGE_RULE = {'rule_id': '2952',
 'domain': 'wlt.gxzf.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'guangxi_culture_leader_cards_v2',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guangxi_culture_gov_leader_list_v2',
 'leader_region_selector': '.gov-leader-list > li:has(a[href] span)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.gov-leader-list > li a[href]',
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
 'risk_flag': '领导卡片当前为“姓名+党组职务”或“姓名+自治区纪委监委驻厅职务”；姓名含排版空格，必须按明确职务前缀拆分。',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.gov-leader-list > li:has(a[href] span)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.gov-leader-list > li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析广西壮族自治区文化和旅游厅领导列表。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    duty_markers = ("党组", "自治区纪委")
    for item in soup.select(".gov-leader-list > li:has(a[href] span)"):
        link = item.select_one("a[href]")
        span = item.select_one("span")
        raw_text = " ".join(span.get_text(" ", strip=True).split()) if span else ""
        marker_positions = [raw_text.find(marker) for marker in duty_markers if raw_text.find(marker) > 0]
        if not marker_positions:
            continue
        split_at = min(marker_positions)
        name = re.sub(r"(?:同志|先生|女士)$", "", _clean_text(raw_text[:split_at]))
        duty = _clean_text(raw_text[split_at:])
        if not name or not duty or len(name) > 4:
            continue
        detail_url = urljoin(source_url, link.get("href", "")) if link else ""
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule.get("parser", ""),
                "selector_summary": "strategy=css；leader=.gov-leader-list > li:has(a[href] span)；name/duty=split_before_党组_or_自治区纪委；依据说明仅保留职务；detail=.gov-leader-list > li a[href]；api_enabled=False",
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
