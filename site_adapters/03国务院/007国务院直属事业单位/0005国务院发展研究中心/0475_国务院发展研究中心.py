from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析国务院发展研究中心“中心领导”职务分组表格。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_url = final_url

    for duty_node in soup.select("strong.leadertext"):
        duty = clean_text(duty_node.get_text(" ", strip=True)).rstrip("：:")
        if not duty:
            continue
        group_row = duty_node.find_parent("tr")
        if not group_row:
            continue
        current = group_row.find_next_sibling("tr")
        while current:
            if current.select_one("strong.leadertext"):
                break
            for link in current.select("a.a14[href]"):
                name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
                if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                    continue
                key = (name, duty)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": urljoin(source_url, str(link.get("href") or "")) if source_url else "",
                        "evidence": duty,
                        "confidence": "high",
                        "parser": "page_inline_drc_gov_leader_group_table_v1",
                    }
                )
            current = current.find_next_sibling("tr")
    return rows


PAGE_RULE = {'rule_id': '0475',
 'domain': 'www.drc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_drc_gov_leader_group_table_v1',
 'leader_region_selector': 'strong.leadertext parent tr + following tr',
 'name_selector': "a.a14[href*='brief.aspx?expertid=']",
 'duty_selector': 'strong.leadertext',
 'detail_link_selector': "a.a14[href*='brief.aspx?expertid=']",
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
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'strong.leadertext parent tr + following tr',
                     'name_selector': "a.a14[href*='brief.aspx?expertid=']",
                     'duty_selector': 'strong.leadertext',
                     'detail_link_selector': "a.a14[href*='brief.aspx?expertid=']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


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
