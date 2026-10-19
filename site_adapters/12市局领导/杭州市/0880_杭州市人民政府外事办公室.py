from __future__ import annotations

import re
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
    "rule_id": "0880",
    "page_type": "人物表格页",
    "structure_group": "hangzhou_foreign_affairs_leader_team_tab_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_foreign_affairs_leader_team_tab_v1",
    "leader_region_selector": "#con_one_2 table.jgzn",
    "name_selector": "人物标题灰底单元格strong",
    "duty_selector": "人物标题灰底单元格姓名后的原始文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "部分人物表格没有头像行，按灰底人物标题单元格定位以兼容首行和第二行两种结构",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导班子标签页内人物标题单元格的DOM顺序解析。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for table in soup.select("#con_one_2 table.jgzn"):
        heading_cell = table.select_one("td[style*='background']")
        person_node = heading_cell.select_one("strong") if heading_cell else None
        if person_node is None:
            continue
        raw_name = clean_text(person_node.get_text(" ", strip=True))
        name = compact_name(raw_name)
        full_text = clean_text(heading_cell.get_text(" ", strip=True))
        duty = full_text[len(raw_name) :].strip() if full_text.startswith(raw_name) else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "#con_one_2 table.jgzn灰底人物标题单元格strong及同行后续职务文本",
            }
        )
    if not records:
        raise ValueError("未在市外办领导班子标签页中解析到有效人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
