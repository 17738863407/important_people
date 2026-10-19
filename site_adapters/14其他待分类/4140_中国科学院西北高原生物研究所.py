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


PAGE_RULE = {"rule_id": "4140", "page_type": "leader_text", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "当前领导正文的居中文本行以姓名结尾，页面未给出个人详情页。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.trs_editor_view")
    rows: list[dict] = []
    for node in content.select("p") if content else []:
        text = "".join(node.get_text(" ", strip=True).split())
        match = re.fullmatch(r"(.+?)([\u4e00-\u9fff]{2,3})", text)
        if match and "所" in match.group(1):
            duty, name = match.groups()
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导正文未解析出姓名和职务")
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
