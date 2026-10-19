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


PAGE_RULE = {"rule_id": "4158", "page_type": "leader_text", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "medium", "risk_notes": "旧式正文将主任、副主任职务标签与人员姓名分置相邻段落，按页面顺序配对。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("p")
    rows: list[dict] = []
    director = next((p.get_text(" ", strip=True) for p in paragraphs if "主任" in p.get_text() and "郭" in p.get_text()), "")
    match = re.search(r"主任\s*[：:]\s*([\u4e00-\u9fff]{2,4})", director)
    if match:
        rows.append({"name": match.group(1), "duty": "主任", "detail_url": ""})
    role_text = next((p.get_text(" ", strip=True) for p in paragraphs if "执行主任" in p.get_text() and "副主任" in p.get_text()), "")
    roles = re.findall(r"执行主任|副主任", role_text)
    names_text = next((p.get_text(" ", strip=True) for p in paragraphs if "研究员" in p.get_text()), "")
    names = re.findall(r"([\u4e00-\u9fff]{2,4})\s*研究员", names_text)
    for name, duty in zip(names, roles):
        rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导正文未解析出可验证的姓名和职务")
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
