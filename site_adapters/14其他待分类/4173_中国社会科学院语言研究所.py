from __future__ import annotations
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找包含 crawler_core 的项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4173", "page_type": "现任领导卡片页", "load_mode": "静态HTML直出",
    "extract_mode": "list_direct", "parser": "page_inline_ling_leader_cards_v1",
    "leader_region_selector": "body", "name_selector": "", "duty_selector": "",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """仅在正文“现任领导”锚点后的相邻姓名、职务节点中提取记录。"""
    from bs4 import BeautifulSoup

    lines = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = max(index for index, line in enumerate(lines) if line == "现任领导")
    rows: list[dict] = []
    for index in range(start + 1, len(lines) - 1):
        name = "".join(lines[index].split())
        duty = lines[index + 1].strip()
        if 2 <= len(name) <= 4 and all("\u4e00" <= char <= "\u9fff" for char in name) and any(
            token in duty for token in ("书记", "所长")
        ):
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
