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
    "rule_id": "4349",
    "page_type": "首页领导成员分组",
    "structure_group": "confucius_foundation_leader_groups_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_confucius_foundation_v1",
    "leader_region_selector": ".jg_right .cy_list",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物兼任多个职务时按网页分组顺序合并；独立兼任标记不写入职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "explicit_leader_group",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从第七届理事会领导成员区提取各职务组。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".jg_right .cy_list")
    if region is None or "第七届理事会" not in region.get_text(" ", strip=True):
        raise RuntimeError("未定位到中国孔子基金会第七届理事会领导成员区")
    merged: dict[str, dict] = {}
    for paragraph in region.select("p"):
        label = paragraph.select_one("span")
        if label is None:
            continue
        duty = re.sub(r"\s+", "", label.get_text(" ", strip=True)).rstrip("：:")
        full_text = " ".join(paragraph.get_text(" ", strip=True).split())
        names_text = full_text[len(" ".join(label.get_text(" ", strip=True).split())):].strip()
        names_text = re.sub(r"[（(]兼[）)]", "", names_text)
        for value in names_text.split("、"):
            name = re.sub(r"\s+", "", value)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                continue
            if name not in merged:
                merged[name] = {"name": name, "duty": duty, "detail_url": ""}
            elif duty not in merged[name]["duty"].split("；"):
                merged[name]["duty"] += "；" + duty
    if not merged:
        raise RuntimeError("领导成员区存在，但未解析到有效姓名与职务")
    return list(merged.values())


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
