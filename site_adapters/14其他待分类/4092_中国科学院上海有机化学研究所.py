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
    "rule_id": "4092", "page_type": "领导卡片页", "structure_group": "sioc_xrld_name_desc_card",
    "reuse_scope": "page_structure", "load_mode": "静态HTML直出", "extract_mode": "list_direct",
    "parser": "page_inline_sioc_xrld_name_desc_card", "leader_region_selector": ".xrld-a",
    "risk_flag": "卡片第二行是职称，依据说明仅保存首行职务；卡片链接为当前页锚点",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片 DOM 顺序读取姓名及首个职务段落。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".xrld-a"):
        name_node = card.select_one(".xrld-name")
        duty_node = card.select_one(".xrld-desc p")
        if name_node is None or duty_node is None:
            continue
        name, duty = name_node.get_text(" ", strip=True), duty_node.get_text(" ", strip=True)
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty})
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
