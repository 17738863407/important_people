from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2959',
 'domain': 'wlt.xinjiang.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V008_text_name_nextline_duty_v1',
 'leader_region_selector': 'body',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': "a[href*='ld']",
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
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': "a[href*='ld']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'success_dir', 'behavior_changed': False}}}


def _clean_duty(value: str) -> str:
    """移除字段标签和无语义的独立兼职标记，保留有效任职限定语。"""
    duty = " ".join(str(value or "").replace("\xa0", " ").split())
    duty = duty.removeprefix("职务:").removeprefix("职务：").strip()
    return duty.replace("（兼职）", "").replace("(兼职)", "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前领导卡片的姓名链接与同卡职务字段提取。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("td > div[align='left']"):
        name_node = card.select_one("a > span.titlestyle63817")
        duty_node = card.select_one("div.summarystyle63817")
        if not name_node or not duty_node:
            continue
        name = "".join(name_node.get_text(" ", strip=True).split())
        duty_text = " ".join(
            text.strip() for text in duty_node.find_all(string=True)
            if text.strip() and not text.find_parent("a")
        )
        duty = _clean_duty(duty_text)
        if not name or not duty:
            continue
        detail_link = name_node.find_parent("a", href=True)
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": urljoin(final_url, detail_link["href"]) if detail_link else "",
            "parser": "xinjiang_culture_leader_card_v1",
            "selector_summary": "td > div[align=left] 内 titlestyle63817 姓名与 summarystyle63817 职务",
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
