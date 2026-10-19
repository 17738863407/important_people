from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2964",
    "page_type": "职务分组名单页",
    "structure_group": "wrsa_numbered_leadership_table_v2",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_wrsa_numbered_leadership_table_v2",
    "leader_region_selector": "包含编号职务分组标题的理事会名单表格",
    "name_selector": "tr td",
    "duty_selector": "tr td[colspan='4']",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "按同表顺序解析职务分组并排除末尾理事组；同一姓名跨其余分组时保留首次顺序并动态合并职务证据",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按表格顺序解析核心领导并排除理事组，同名跨组时合并职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find(
        string=lambda value: value
        and re.fullmatch(r"\s*[一二三四五六七八九十]+、会长\s*", value)
    )
    table = title_node.find_parent("table") if title_node else None
    if table is None:
        return []

    groups: list[tuple[str, str, list[str]]] = []
    current_duty = ""
    current_evidence = ""
    current_names: list[str] = []
    for table_row in table.select("tr"):
        row_text = re.sub(r"\s+", "", table_row.get_text(" ", strip=True))
        duty_match = re.fullmatch(
            r"(?:[一二三四五六七八九十]+、)?(会长|副会长|秘书长|副秘书长|理事|海外理事)(?:（[^）]*）)?：?",
            row_text,
        )
        if duty_match is not None:
            if current_duty and current_names:
                groups.append((current_duty, current_evidence, current_names))
            current_duty = duty_match.group(1)
            current_evidence = current_duty
            current_names = []
            continue
        if not current_duty:
            continue
        for cell in table_row.select(":scope > td"):
            name = re.sub(r"（[^）]*）|\([^)]*\)", "", cell.get_text(" ", strip=True))
            name = re.sub(r"\s+", "", name)
            name = name.replace("・", "·").replace("•", "·")
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                current_names.append(name)
    if current_duty and current_names:
        groups.append((current_duty, current_evidence, current_names))

    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for duty, evidence, names in groups:
        if duty == "理事":
            continue
        for name in names:
            existing = row_by_name.get(name)
            if existing is not None:
                existing_duties = existing["duty"].split("；")
                existing_evidence = existing["evidence"].split("；")
                if evidence not in existing_duties:
                    existing["duty"] += f"；{evidence}"
                if evidence not in existing_evidence:
                    existing["evidence"] += f"；{evidence}"
                continue
            record = {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_wrsa_numbered_leadership_table_v2",
            }
            row_by_name[name] = record
            rows.append(record)
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
