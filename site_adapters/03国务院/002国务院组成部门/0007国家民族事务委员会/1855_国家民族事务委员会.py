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

PAGE_RULE = {'rule_id': '1855',
 'domain': 'www.neac.gov.cn',
 'page_type': '人物列表完整页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'neac_leader_parser_v1',
 'source_parser': 'card_person_parser_v1',
 'leader_region_selector': '.w1-3, .p3, .mz_list',
 'name_selector': 'b',
 'duty_selector': 'span',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': [],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按原领导区域内卡片逐项绑定姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(".w1-3 li a[href], .p3 li a[href], .mz_list li a[href]"):
        name_node = link.select_one("b")
        duty_node = link.select_one("span")
        name = "".join(name_node.stripped_strings).replace("　", "").replace(" ", "") if name_node else ""
        duty = " ".join(duty_node.stripped_strings).strip() if duty_node else ""
        if not name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "selector_summary": "领导区域li a内b姓名+span职务",
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
