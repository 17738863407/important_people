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
    "rule_id": "4167",
    "page_type": "协会领导机构公示页",
    "structure_group": "cas_retired_science_association_officer_text",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cas_retired_science_association_v1",
    "leader_region_selector": "article, .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面后续含理事、监事和工作委员会成员；仅取第十届理事会领导成员段落。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从第十届理事会领导成员段落动态解析协会领导。"""
    from bs4 import BeautifulSoup

    lines = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = next((index for index, line in enumerate(lines) if "第十届理事会领导成员" in line), None)
    if start is None:
        return []
    end = next((index for index, line in enumerate(lines[start + 1 :], start + 1) if "常务理事" in line), len(lines))
    labels = {"顾问", "理事长", "副理事长", "秘书长", "副秘书长"}
    people: dict[str, dict] = {}
    index = start + 1
    while index < end:
        compact_line = re.sub(r"\s+", "", lines[index])
        duty = next((label for label in labels if compact_line == label or compact_line.startswith(f"{label}：") or compact_line.startswith(f"{label}:")), "")
        if not duty:
            index += 1
            continue
        next_index = index + 1
        values: list[str] = [re.sub(rf"^{re.escape(duty)}\s*[：:]", "", lines[index])]
        while next_index < end and not any(re.sub(r"\s+", "", lines[next_index]).startswith(label) for label in labels):
            values.append(lines[next_index])
            next_index += 1
        raw_names = re.sub(rf"^{re.escape(duty)}\s*[：:]", "", " ".join(values)).lstrip("：: ")
        for raw_name in re.split(r"[\u2002\u3000]{2,}|\s{3,}|[、,，]", raw_names):
            name = re.sub(r"[（(][^）)]*[）)]|\s+", "", raw_name)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                item = people.setdefault(name, {"name": name, "duties": []})
                if duty not in item["duties"]:
                    item["duties"].append(duty)
        index = next_index
    return [
        {"name": item["name"], "duty": "；".join(item["duties"]), "detail_url": ""}
        for item in people.values()
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
