from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造仅包含技术定位信息的页面规则。"""
    return {'rule_id': rule_id,
 'domain': 'district.ce.cn',
 'page_type': '人物列表完整页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ce_district_leader_parser_v1',
 'source_parser': 'card_person_parser_v1',
 'leader_region_selector': '.main .left2:has(> h3 > a[href="./sw/"]) .ren2',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def extract_party_committee_section(html: str) -> str:
    """仅保留“市委领导”板块，避免相邻的市政府领导名单混入。"""
    soup = BeautifulSoup(html, "html.parser")
    title_link = soup.select_one('.main .left2 > h3 > a[href="./sw/"]')
    section = title_link.find_parent("div", class_="left2") if isinstance(title_link, Tag) else None
    if not isinstance(section, Tag):
        raise RuntimeError("未定位到重庆市委领导板块，停止输出以避免误采市政府领导")
    return f'<div class="main">{section}</div>'


def parse_party_committee_rows(
    section_html: str,
    page_rule: dict[str, object],
) -> list:
    """按市委名单表格的每个 ``tr`` 独立解析，防止末尾相邻人员粘连。"""
    from crawler_core.parsers_v1 import make_record

    soup = BeautifulSoup(section_html, "html.parser")
    rows = []
    for table_row in soup.select("tr"):
        cells = table_row.find_all(["td", "th"], recursive=False)
        name_link = table_row.select_one("a[href]")
        name_cell = name_link.find_parent(["td", "th"]) if isinstance(name_link, Tag) else None
        if not isinstance(name_cell, Tag) or name_cell not in cells:
            continue

        name = " ".join(name_link.get_text(" ", strip=True).split())
        name_cell_index = cells.index(name_cell)
        duty = " ".join(
            cell_text
            for cell in cells[name_cell_index + 1:]
            if (cell_text := " ".join(cell.get_text(" ", strip=True).split()))
        )
        record = make_record(
            rule=page_rule,
            name=name,
            duty=duty,
            evidence=f"{name} {duty}",
            parser=str(page_rule.get("parser", "ce_district_leader_parser_v1")),
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    if not rows:
        raise RuntimeError("重庆市委领导表格解析结果为空，停止输出以避免生成错误名单")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list:
    """限定市委板块并按表格行解析，再将网页原始职务映射到依据说明。"""
    party_committee_html = extract_party_committee_section(html)
    rows = parse_party_committee_rows(party_committee_html, page_rule)
    for row in rows:
        row.evidence = row.duty
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "0449"
    main(rule_id_value)
