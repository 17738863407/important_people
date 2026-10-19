from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3925",
    "page_type": "职务标题与多人表格",
    "structure_group": "anshun_cppcc_grouped_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_anshun_cppcc_table_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".content-txt table",
    "name_selector": "职务标题行后的非空td",
    "duty_selector": "独立主席/副主席/秘书长标题行",
    "detail_link_selector": "none_article_table",
    "risk_flag": "姓名后带民族、党派等括注；括注只用于名单展示，不属于职务",
    "confidence": "high",
}


def compact_text(value: object) -> str:
    """删除表格为字间距插入的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名后的独立民族、性别、党派展示括注。"""
    text = compact_text(value)
    return re.sub(r"[（(][^（）()]*[）)]$", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按表格行列顺序继承职务标题并拆分多人名单。"""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(".content-txt table")
    if table is None:
        raise RuntimeError("未定位到政协主席、副主席、秘书长名单表格")

    rows: list[dict] = []
    seen_names: set[str] = set()
    current_duty = ""
    valid_duties = {"主席", "副主席", "秘书长"}
    for table_row in table.select("tr"):
        values = [compact_text(cell.get_text(" ", strip=True)) for cell in table_row.find_all(["td", "th"], recursive=False)]
        nonempty = [value for value in values if value]
        if len(nonempty) == 1 and nonempty[0].rstrip("：:") in valid_duties:
            current_duty = nonempty[0].rstrip("：:")
            continue
        if not current_duty:
            continue
        for value in values:
            name = clean_name(value)
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
                    "selector_summary": ".content-txt表格职务标题行及后续非空td",
                }
            )

    if not rows:
        raise RuntimeError("政协领导名单表格未提取到有效人物")
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
