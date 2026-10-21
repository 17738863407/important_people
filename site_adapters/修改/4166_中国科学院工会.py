from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找包含 crawler_core 的项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4166",
    "page_type": "委员会成员公示页",
    "structure_group": "cas_union_officer_text",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cas_union_officer_v1",
    "leader_region_selector": "article, .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时列出常委、委员及经审委名单，仅取工会委员会主席、副主席字段。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """动态解析工会委员会主席、常务副主席和副主席。"""
    from bs4 import BeautifulSoup

    lines = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = next((index for index, line in enumerate(lines) if re.sub(r"\s+", "", line) == "主席"), None)
    if start is None:
        return []
    end = next(
        (index for index, line in enumerate(lines[start + 1 :], start + 1) if "常务委员会委员" in re.sub(r"\s+", "", line)),
        len(lines),
    )
    rows: list[dict] = []
    labels = {"主席", "常务副主席", "副主席"}
    index = start
    while index < end:
        duty = re.sub(r"\s+", "", lines[index])
        if duty not in labels:
            index += 1
            continue
        next_index = index + 1
        value_parts: list[str] = []
        while next_index < end and re.sub(r"\s+", "", lines[next_index]) not in labels:
            value_parts.append(lines[next_index])
            next_index += 1
        raw_names = " ".join(value_parts).lstrip("：: ")
        for raw_name in re.split(r"\s{3,}|[、,，]", raw_names):
            name = re.sub(r"\s+", "", raw_name)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                rows.append({"name": name, "duty": duty, "detail_url": ""})
        index = next_index
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
