from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1082",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "main#globalMain",
    "item_selector": "main#globalMain p",
    "risk_note": "每个人物由基本信息、现任职务和分工段落组成，职务必须限定在当前人物块。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩正文中的排版空白。"""
    return re.sub(r"[\s\u3000\u2003\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物基本信息段落划分边界并提取完整“现任”原句。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(page_rule["leader_region_selector"])
    if main is None:
        return []

    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in main.select("p")]
    person_pattern = re.compile(r"^([\u4e00-\u9fff·]{2,8})，(?:男|女)，")
    rows: list[dict] = []

    for index, text in enumerate(paragraphs):
        person_match = person_pattern.match(text)
        if not person_match:
            continue

        evidence = ""
        for candidate in paragraphs[index + 1 :]:
            if person_pattern.match(candidate):
                break
            current_match = re.search(r"现任[^。]*。", candidate)
            if current_match:
                evidence = re.sub(r"^现任\s*", "", current_match.group(0)).rstrip("。 ")
                break
        if not evidence:
            continue

        rows.append(
            {
                "name": person_match.group(1),
                "duty": "",
                "evidence": evidence,
                "detail_url": "",
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
