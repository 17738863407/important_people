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
    "rule_id": "4164",
    "page_type": "机构简介页",
    "structure_group": "ecas_office_staff_text",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_ecas_office_staff_v1",
    "leader_region_selector": "article, .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "组成名单为正文文本，需从‘网信办组成’锚点起提取主任和副主任，排除成员席位名单。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """动态解析当前页面网信办组成中的主任、副主任。"""
    from bs4 import BeautifulSoup

    lines = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = next((index for index, line in enumerate(lines) if "网信办组成" in line), None)
    if start is None:
        return []
    end = next(
        (index for index, line in enumerate(lines[start + 1 :], start + 1) if "成员" in re.sub(r"\s+", "", line)),
        len(lines),
    )
    segment = " ".join(lines[start + 1 : end])
    rows: list[dict] = []
    for duty, names in re.findall(r"(副主任|主\s*任)\s*[：:]\s*([^：:]+?)(?=(?:副主任|主\s*任)\s*[：:]|$)", segment):
        clean_duty = re.sub(r"\s+", "", duty)
        for matched_name in re.finditer(
            r"(?P<name>[\u4e00-\u9fff·]{2,20})(?P<qualifier>[（(][^）)]{1,8}[）)])?",
            names,
        ):
            name = matched_name.group("name")
            qualifier = matched_name.group("qualifier") or ""
            evidence = f"{clean_duty}{qualifier}"
            rows.append({"name": name, "duty": evidence, "detail_url": ""})
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
