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

PAGE_RULE = {'rule_id': '2010',
 'domain': 'www.nxrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_nxrd_leader_link_text_v1',
 'leader_region_selector': 'a[href*="/rdgk/ldzc/cwhld/"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"static_http","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a[href*="/rdgk/ldzc/cwhld/"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染后的常委会领导链接文本含职务和姓名'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen_names = set()
    for link in soup.select('a[href*="/rdgk/ldzc/cwhld/"]'):
        text = clean_text(link.get_text(" ", strip=True))
        if "：" not in text:
            continue
        duty, name = [clean_text(part) for part in text.split("：", 1)]
        name = name.replace(" ", "")
        if duty not in {"主任", "副主任", "秘书长"} or not name or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": urljoin(final_url or page_rule["url"], link.get("href", "")),
            "evidence": duty,
            "selector_summary": "常委会领导链接文本：职务：姓名",
        })
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
