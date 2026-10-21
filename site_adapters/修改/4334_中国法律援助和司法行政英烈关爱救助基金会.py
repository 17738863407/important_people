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
    "rule_id": "4334",
    "page_type": "理事会分组名单页",
    "structure_group": "claf_council_paragraph_groups_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_claf_council_v1",
    "leader_region_selector": ".jgsz",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "以理事长、副理事长、理事三个网页分组为职务证据；成员行后的外部履历不写入基金会职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "paragraph_group_state_machine",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按网页分组顺序提取第五届理事会成员。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".jgsz")
    if region is None or "第五届理事会" not in region.get_text(" ", strip=True):
        raise RuntimeError("未定位到基金会第五届理事会正文")

    rows: list[dict] = []
    current_duty = ""
    for paragraph in region.find_all("p", recursive=False):
        raw = paragraph.get_text("", strip=False).replace("\u3000", " ")
        compact = re.sub(r"\s+", "", raw)
        if compact.startswith("副理事长"):
            current_duty = "副理事长"
            continue
        if compact.startswith("理事长"):
            current_duty = "理事长"
            continue
        if compact.startswith("理事（以下按姓氏笔画排列）"):
            current_duty = "理事"
            continue
        if not current_duty:
            continue
        parts = raw.strip().rsplit("\u00a0 \u00a0\u00a0", 1)
        if len(parts) != 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            rows.append({"name": name, "duty": current_duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("理事会正文存在，但未解析到分组成员")
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
