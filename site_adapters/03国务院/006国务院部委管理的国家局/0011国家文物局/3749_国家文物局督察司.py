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
    "rule_id": "3749", "page_type": "内设机构负责人页", "structure_group": "ncha_responsible_section_v1",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_inline_ncha_responsible_section_v1", "leader_region_selector": "#zoom", "name_selector": "#zoom p",
    "duty_selector": "#zoom p", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high", "filter_policy": "strong_no_wordlist", "risk_flag": "只解析负责人至主要职责标题之间的职务冒号人员段落，性别括注不写入姓名",
    "locator_strategy": "zoom_responsible_to_main_duties_paragraphs",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("#zoom")
    start = next((p for p in container.find_all("p", recursive=False) if "负责人" in clean_text(p.get_text(" ", strip=True))), None) if container else None
    if start is None:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in start.find_next_siblings("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "主要职责" in text:
            break
        match = re.fullmatch(r"(.+?)[：:]\s*(.+)", text)
        if match is None:
            continue
        duty = clean_text(match.group(1)).replace("、", "；")
        for raw_name in re.split(r"[、,，]", match.group(2)):
            name = re.sub(r"[（(][^）)]*[）)]", "", clean_text(raw_name)).replace(" ", "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "scope=responsible_to_main_duties；order=paragraph_then_name_order"})
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
