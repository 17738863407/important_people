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
    "rule_id": "4343",
    "page_type": "理事会负责人文章页",
    "structure_group": "cfej_chair_bio_blocks_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_cfej_chairs_v1",
    "leader_region_selector": ".TRS_Editor",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "文章还列常务理事和理事；仅提取主席、副主席两个负责人分组。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "direct_child_group_state_machine",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按文章直属块顺序提取主席和副主席姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError("未定位到第四届理事会文章正文")
    rows: list[dict] = []
    current_duty = ""
    for child in region.find_all(recursive=False):
        text = " ".join(child.get_text(" ", strip=True).split())
        if text == "主席：":
            current_duty = "主席"
            continue
        if text == "副主席：":
            current_duty = "副主席"
            continue
        if text.startswith("常务理事："):
            break
        name = re.sub(r"\s+", "", text)
        if current_duty and re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            rows.append({"name": name, "duty": current_duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("负责人分组存在，但未解析到主席或副主席姓名")
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
