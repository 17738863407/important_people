from __future__ import annotations

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

PAGE_RULE = {'rule_id': '3193',
 'domain': 'yjgl.guizhou.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'GuizhouEmergencyLeaderDtLinkParser_v1',
 'leader_region_selector': '.zfxxgk_zdgkc dl a[href]',
 'name_selector': 'a[title] or text after colon',
 'duty_selector': 'text before colon',
 'detail_link_selector': '.zfxxgk_zdgkc dl a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_zdgkc dl a[href]',
                     'name_selector': 'a[title] or text after colon',
                     'duty_selector': 'text before colon',
                     'detail_link_selector': '.zfxxgk_zdgkc dl a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析贵州省应急管理厅领导链接列表。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(rule.get("url", "")) or base_url
    records: list[dict] = []
    for link in soup.select(".zfxxgk_zdgkc dl a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        duty, text_name = text.replace(":", "：").split("：", 1)
        name = _clean_text(link.get("title") or text_name)
        duty = _clean_text(duty).replace(";", "；")
        if not name or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(source_url, link.get("href", "")),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "strategy=css；leader=.zfxxgk_zdgkc dl a[href]；name=a[title]/冒号后文本；duty=冒号前文本；detail=a[href]",
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
