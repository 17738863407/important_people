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
    "rule_id": "3732", "page_type": "直属单位职能页部门领导", "structure_group": "cma_department_leaders_v1",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_inline_cma_department_leaders_v1", "leader_region_selector": ".TRS_UEDITOR",
    "name_selector": ".TRS_UEDITOR p span span", "duty_selector": ".TRS_UEDITOR p", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "须以部门领导强标题至下一强标题划界，保留党委、纪委及台长等多项现职",
    "locator_strategy": "page_inline_heading_bounded_paragraphs",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".TRS_UEDITOR")
    if container is None:
        return []
    heading = next((node for node in container.select("p strong") if "部门领导" in clean_text(node.get_text(" ", strip=True))), None)
    current = heading.find_parent("p") if heading is not None else None
    if current is None:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in current.find_next_siblings("p"):
        if paragraph.find("strong") is not None:
            break
        name_node = paragraph.select_one("span span")
        if name_node is None:
            continue
        name_text = clean_text(name_node.get_text(" ", strip=True))
        name = name_text.replace(" ", "")
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        duty = full_text[len(name_text):].strip().replace("、", "；") if full_text.startswith(name_text) else ""
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "scope=department_leaders_heading；order=paragraph_order"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
