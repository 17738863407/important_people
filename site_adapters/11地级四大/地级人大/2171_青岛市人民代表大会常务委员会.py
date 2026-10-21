from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2171",
    "page_type": "职务分组名单页",
    "structure_group": "qingdao_renda_composition_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": ".trs_editor_view table tr > td",
    "duty_selector": ".trs_editor_view table tr > td",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".trs_editor_view"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "委员标题与委员姓名分处连续表格行，必须继承当前职务分组并保持网页原始顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(value: str) -> str:
    """删除表格排版空白，保留姓名与职务的原始字词。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def _extract_role(value: str) -> str:
    """识别组成人员表格中的四类职务标题。"""
    role = _compact_text(value).rstrip("：:")
    if role.startswith("委员（按姓名笔画为序）"):
        return "委员"
    return role if role in {"主任", "副主任", "秘书长"} else ""


def _extract_name(value: str) -> str:
    """清理名单中的性别标记并校验姓名格式。"""
    name = re.sub(r"(?:\(女\)|（女）)$", "", _compact_text(value))
    return name if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页表格行和单元格顺序抽取全部常委会组成人员。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".trs_editor_view")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    current_role = ""
    for table_row in region.select("tr"):
        cells = table_row.find_all("td", recursive=False)
        role_index = -1
        for index, cell in enumerate(cells):
            detected_role = _extract_role(cell.get_text(" ", strip=True))
            if detected_role:
                current_role = detected_role
                role_index = index
                break
        if not current_role:
            continue
        if current_role == "委员":
            continue
        candidate_cells = cells[role_index + 1 :] if role_index >= 0 else cells
        for cell in candidate_cells:
            name = _extract_name(cell.get_text(" ", strip=True))
            if not name:
                continue
            key = (name, current_role)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": current_role,
                    "evidence": current_role,
                    "detail_url": "",
                }
            )

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
