from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3929",
    "page_type": "跨行职务名单表格",
    "structure_group": "chaozhou_cppcc_roster_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_chaozhou_cppcc_table_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".con_detail table.ke-zeroborder",
    "name_selector": "职务列后的非空td",
    "duty_selector": "首列主席/副主席/秘书长",
    "detail_link_selector": "none_article_table",
    "risk_flag": "副主席名单跨两行，第二行首列为空；必须继承上一有效职务",
    "confidence": "high",
}


def compact_text(value: object) -> str:
    """删除名单表格中的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按表格行列顺序继承首列职务并读取姓名。"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(".con_detail table.ke-zeroborder")
    if table is None:
        raise RuntimeError("未定位到政协领导班子表格")

    rows: list[dict] = []
    seen_names: set[str] = set()
    current_duty = ""
    valid_duties = {"主席", "副主席", "秘书长"}
    for table_row in table.select("tr"):
        values = [compact_text(cell.get_text(" ", strip=True)) for cell in table_row.find_all(["td", "th"], recursive=False)]
        if not values:
            continue
        if values[0] in valid_duties:
            current_duty = values[0]
        if not current_duty:
            continue
        for name in values[1:]:
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "evidence": current_duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": ".con_detail领导表格首列职务及后续姓名单元格",
                }
            )

    if not rows:
        raise RuntimeError("政协领导班子表格未提取到有效人物")
    return rows


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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
