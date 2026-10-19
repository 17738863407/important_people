from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4505",
    "page_type": "纪委监委领导机构表格",
    "structure_group": "liaoning_discipline_supervision_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "table_role_rows",
    "parser": "page_liaoning_discipline_supervision_table_v1",
    "leader_region_selector": "table.ldjg2021",
    "name_selector": "tr中职务列之后的姓名单元格",
    "duty_selector": "td.biaod",
    "detail_link_selector": "姓名单元格内a[href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "同表含纪委委员及监委委员行；只解析书记、副书记、常务委员会委员、主任、副主任并按首次出现合并。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按表格原始行序提取允许职务，并合并纪委、监委同人任职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.select_one("table.ldjg2021")
    if table is None:
        raise RuntimeError("未找到领导机构表格 table.ldjg2021")
    allowed = {"书记", "副书记", "常务委员会委员", "主任", "副主任"}
    subject = ""
    current_role = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    details: dict[str, str] = {}
    for tr in table.select("tr"):
        subject_node = tr.select_one("td.ldjgtit2")
        if subject_node is not None:
            subject = re.sub(r"\s+", "", subject_node.get_text(" ", strip=True))
            current_role = ""
            continue
        role_node = tr.select_one("td.biaod")
        role = re.sub(r"\s+", "", role_node.get_text(" ", strip=True) if role_node else "")
        if role:
            current_role = role if role in allowed else ""
        if not subject or current_role not in allowed:
            continue
        cells = tr.find_all("td", recursive=False)
        for cell in cells[2:]:
            name = re.sub(r"[\s\u00a0\u3000]+", "", cell.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name not in duties:
                duties[name] = []
                details[name] = ""
                order.append(name)
            evidence = f"{subject}{current_role}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
            link = cell.select_one("a[href]")
            if link is not None and not details[name]:
                details[name] = urljoin(final_url, str(link.get("href") or ""))
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": details[name], "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "table.ldjg2021按主体行与td.biaod允许职务行解析；委员行排除；同人按首次出现合并"} for name in order]
    if not rows:
        raise RuntimeError("领导机构表格未提取到允许职务人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
