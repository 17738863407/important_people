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
    "rule_id": "4165",
    "page_type": "组织成员公示页",
    "structure_group": "cas_youth_committee_text",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cas_youth_committee_v1",
    "leader_region_selector": "article, .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "委员会名单包含委员，当前机构领导仅取书记、副书记字段。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从当前届次委员会公示中动态提取书记和副书记。"""
    from bs4 import BeautifulSoup

    lines = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = next((index for index, line in enumerate(lines) if line.startswith("书") and "记" in line), None)
    if start is None:
        return []
    end = next(
        (index for index, line in enumerate(lines[start + 1 :], start + 1) if "委员" in re.sub(r"\s+", "", line)),
        len(lines),
    )
    segment = " ".join(lines[start:end])
    rows: list[dict] = []
    for duty, names in re.findall(r"(副书记|书\s*记)\s*[：:]\s*([^：:]+?)(?=(?:副书记|书\s*记)\s*[：:]|$)", segment):
        clean_duty = re.sub(r"\s+", "", duty)
        for name in re.findall(r"[\u4e00-\u9fff·]{2,20}", re.sub(r"\s+", "", names)):
            rows.append({"name": name, "duty": clean_duty, "detail_url": ""})
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
