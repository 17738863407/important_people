from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4160", "page_type": "leader_text", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "正文“主要领导”段落按职务：姓名列表展示，未提供个人详情页。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    people: dict[str, dict] = {}
    for paragraph in soup.select("p"):
        text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(r"(主任|副主任|总工程师|副总工程师|首席科学家)[：:]\s*(.+)", text)
        if match is None:
            continue
        duty, names_text = match.groups()
        for name in re.findall(r"[\u4e00-\u9fff]{2,4}", names_text):
            item = people.setdefault(name, {"name": name, "duties": []})
            if duty not in item["duties"]:
                item["duties"].append(duty)
    rows = [
        {"name": item["name"], "duty": "；".join(item["duties"]), "detail_url": ""}
        for item in people.values()
    ]
    if not rows:
        raise RuntimeError("主要领导正文未解析出姓名和职务")
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
