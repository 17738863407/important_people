from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1498',
 'domain': 'www.mct.gov.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'mct_leader_parser_v1',
 'source_parser': 'mct_leader_parser_v1',
 'leader_region_selector': '#zoom, .TRS_Editor, .Custom_UnionStyle, .main_text, .article',
 'name_selector': '.bld_list_tit',
 'duty_selector': '.bld_list_zw',
 'detail_link_selector': '.bld_list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.bld_list a[href]',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按原领导卡片字段逐项映射姓名、职务和独立详情链接。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".bld_list"):
        name_node = card.select_one(".bld_list_tit")
        duty_node = card.select_one(".bld_list_zw")
        link = card.select_one("a[href]")
        name = re.sub(r"[\s\u3000]+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href") or "") if link and final_url else "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "leader=.bld_list；name=.bld_list_tit；duty=.bld_list_zw；detail=.bld_list a[href]",
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
