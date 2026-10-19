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
    "rule_id": "4163",
    "page_type": "机构简介页",
    "structure_group": "nssc_overseas_lab_staff_text",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nssc_overseas_lab_staff_v1",
    "leader_region_selector": "div.TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "主要人员以简介文本呈现，需以‘主要人员’段落边界排除机构介绍与工作人员。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从当前页面“主要人员”段落动态提取具有管理职务的人员。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.TRS_Editor")
    lines = list(container.stripped_strings) if container else []
    start = next((index for index, line in enumerate(lines) if "主要人员" in line), None)
    if start is None:
        return []
    end = next(
        (
            index
            for index, line in enumerate(lines[start + 1 :], start + 1)
            if "了解更多" in line or line.startswith("版权所有")
        ),
        len(lines),
    )
    pattern = re.compile(
        r"^(?P<duty>实验室(?:执行|行政)?(?:副)?主任)\s*[：:]\s*(?P<names>[\u4e00-\u9fff·]{2,20})"
    )
    rows: list[dict] = []
    for line in lines[start + 1 : end]:
        matched = pattern.match(line.replace("（兼）", ""))
        if not matched:
            continue
        rows.append(
            {
                "name": matched.group("names"),
                "duty": matched.group("duty"),
                "detail_url": "",
            }
        )
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
