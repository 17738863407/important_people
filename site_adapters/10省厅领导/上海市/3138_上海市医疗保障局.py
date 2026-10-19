from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3138",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#ivs_content",
    "item_selector": "#ivs_content p",
    "risk_note": "页面脚本会跳转搜索页，须保留原始HTML；姓名后首个非空段落以逗号分隔职务与职责。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按姓名独立段落顺序，提取下一非空段落逗号前的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for paragraph in soup.select(page_rule["item_selector"]):
        name = clean_text(paragraph.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        duty_line = ""
        for sibling in paragraph.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            text = clean_text(sibling.get_text(" ", strip=True))
            if not text:
                continue
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", text):
                break
            duty_line = text
            break
        evidence = re.split(r"[，,]", duty_line, maxsplit=1)[0].strip()
        if not evidence or not any(word in evidence for word in ("党组", "局长", "巡视员")):
            continue
        rows.append(
            {
                "name": name,
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
