from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: object) -> str:
    """合并页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", "", str(value or ""))


def clean_name(value: object) -> str:
    """删除姓名后的性别、民族等人物属性括注。"""
    return re.sub(r"[（(][^）)]*[）)]$", "", clean_text(value))


def section_kind(section_title: str) -> str:
    """根据当前网页分组标题识别纪委或监委。"""
    if "纪律检查委员会" in section_title:
        return "discipline"
    if "监察委员会" in section_title:
        return "supervision"
    return ""


def accepted_roles(kind: str) -> set[str]:
    """限制为页面公开的领导班子，不纳入按笔画排序的全体委员。"""
    if kind == "discipline":
        return {"书记", "副书记", "常委"}
    if kind == "supervision":
        return {"主任", "副主任"}
    return set()


def row_cells(row: Tag) -> list[Tag]:
    """只读取当前表格行的直属单元格，避免畸形 HTML 导致跨行串入。"""
    return [cell for cell in row.find_all(["td", "th"], recursive=False) if isinstance(cell, Tag)]


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按纪委、监委分组抽取领导，并为每项职务保留完整任职主体。"""
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.select_one("table.ryjg")
    if table is None:
        raise RuntimeError("领导机构页面缺少 table.ryjg")

    people: OrderedDict[str, dict[str, object]] = OrderedDict()
    current_section = ""
    current_kind = ""
    current_role = ""

    for row in table.find_all("tr", recursive=False):
        cells = row_cells(row)
        if not cells:
            continue

        heading = row.find("th")
        if heading is not None:
            candidate_section = clean_text(heading.get_text(" ", strip=True))
            candidate_kind = section_kind(candidate_section)
            if candidate_kind:
                current_section = candidate_section
                current_kind = candidate_kind
                current_role = ""
            continue

        role_node = row.find("strong")
        if role_node is not None:
            candidate_role = clean_text(role_node.get_text(" ", strip=True))
            row_text = clean_text(row.get_text(" ", strip=True))
            if "按姓氏笔画排序" in row_text or candidate_role not in accepted_roles(current_kind):
                current_role = ""
                continue
            current_role = candidate_role

        if not current_section or not current_role:
            continue

        duty = current_section + current_role
        for cell in cells[1:]:
            name = clean_name(cell.get_text(" ", strip=True))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
                continue
            record = people.setdefault(name, {"duties": []})
            duties = record["duties"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)

    rows: list[dict[str, str]] = []
    for name, record in people.items():
        duties = record["duties"]
        if not isinstance(duties, list) or not duties:
            continue
        evidence = "；".join(str(duty) for duty in duties)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "table.ryjg 中纪委书记、副书记、常委及监委主任、副主任；"
                    "按分组标题补足完整任职主体；排除按姓氏笔画排序的委员名单"
                ),
            }
        )

    if not rows:
        raise RuntimeError("纪委、监委领导分组未提取到人物")
    return rows


PAGE_RULE = {
    "rule_id": "4489",
    "page_type": "纪委监委领导分组表格",
    "structure_group": "beijing_discipline_supervision_leaders_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "静态HTML",
    "extract_mode": "grouped_table",
    "parser": "page_beijing_discipline_supervision_leaders_v1",
    "leader_region_selector": "table.ryjg",
    "name_selector": "纪委、监委领导职务行中除首列外的姓名单元格",
    "duty_selector": "table.ryjg 分组标题与职务行 strong",
    "detail_link_selector": "页面未提供独立人物详情页，留空",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "排除按姓氏笔画排序的纪委委员名单；同一人物的纪委、监委完整职务按网页首次出现顺序合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


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
