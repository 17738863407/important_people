from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


PAGE_RULE: dict[str, Any] = {
    "rule_id": "3096",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "td.STYLE18",
    "parser_id": "custom_mwr_publicity_center_leaders_v2",
    "structure_group": "组织机构页_姓名冒号职务逐行表格",
    "confidence": "high",
    "risk_notes": "同页另有主要职责和内设机构表格，仅接受全部非空行均符合短姓名加冒号加职务的唯一表格单元格。",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _parse_candidate(cell: Any) -> list[dict[str, str]]:
    lines = [_clean_text(line) for line in cell.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 2:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([\u3400-\u9fff·\s]{2,10})[：:](.+)", line)
        if match is None:
            return []
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or not duty or name in seen:
            return []
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": ""})
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """解析组织机构页中逐行列出的领导班子表格。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates = [
        rows
        for cell in soup.select(page_rule["leader_region_selector"])
        if (rows := _parse_candidate(cell))
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"领导班子候选表格数量异常：{len(candidates)}")
    return candidates[0]


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
