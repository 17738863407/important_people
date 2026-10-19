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
    "rule_id": "4341",
    "page_type": "领导简介职务姓名行",
    "structure_group": "mof_tax_center_leader_lines_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_mof_tax_center_v1",
    "leader_region_selector": ".TRS_Editor, .pages_content",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文把职务和姓名拆为多个span，按同一居中段落合并后解析。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "centered_paragraph_regex",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从同一段落的“副主任+姓名”结构提取中心领导。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        compact = re.sub(r"\s+", "", paragraph.get_text("", strip=True))
        matched = re.fullmatch(r"(副主任)([\u3400-\u9fff·]{2,6})", compact)
        if matched:
            rows.append({"name": matched.group(2), "duty": matched.group(1), "detail_url": ""})
    if not rows:
        raise RuntimeError("领导简介正文未解析到‘副主任+姓名’段落")
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
