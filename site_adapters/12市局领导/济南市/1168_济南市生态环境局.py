from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1168",
    "page_type": "人物表格页",
    "structure_group": "四行一组领导标签表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "custom_zoom_four_row_leader_table_v1",
    "leader_region_selector": "#zoom table",
    "name_selector": "tr（标签为姓名）的下一单元格",
    "duty_selector": "tr（标签为职务）的下一单元格",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#zoom table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css+label",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom table",
            "name_selector": "tr（标签为姓名）的下一单元格",
            "duty_selector": "tr（标签为职务）的下一单元格",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "当前静态HTML已直出完整领导标签表"},
    },
}


def clean_text(text: str) -> str:
    return "".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def extract_label_value(row) -> tuple[str, str]:
    cells = row.find_all(["td", "th"], recursive=False)
    for index, cell in enumerate(cells[:-1]):
        label = clean_text(cell.get_text(" ", strip=True)).rstrip("：:")
        if label in {"姓名", "职务", "领导简历", "工作分工"}:
            return label, clean_text(cells[index + 1].get_text(" ", strip=True))
    return "", ""


def build_row(name: str, duty: str) -> dict:
    return {
        "name": name,
        "duty": duty,
        "evidence": duty,
        "detail_url": "",
        "selector_summary": "#zoom唯一领导表+姓名/职务相邻单元格",
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    del final_url, page_rule
    soup = BeautifulSoup(html or "", "html.parser")
    leader_tables = []
    for table in soup.select("#zoom table"):
        labels = [extract_label_value(row)[0] for row in table.find_all("tr")]
        if labels.count("姓名") >= 1 and labels.count("姓名") == labels.count("职务"):
            leader_tables.append(table)
    if len(leader_tables) != 1:
        raise ValueError(f"预期#zoom内唯一领导标签表，实际命中{len(leader_tables)}个")

    rows: list[dict] = []
    current_name = ""
    current_duty = ""
    for row in leader_tables[0].find_all("tr"):
        label, value = extract_label_value(row)
        if label == "姓名":
            if current_name and current_duty:
                rows.append(build_row(current_name, current_duty))
            current_name = value
            current_duty = ""
        elif label == "职务" and current_name:
            current_duty = value
    if current_name and current_duty:
        rows.append(build_row(current_name, current_duty))
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
