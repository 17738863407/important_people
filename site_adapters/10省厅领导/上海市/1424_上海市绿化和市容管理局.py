from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1424",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#ivs_content",
    "item_selector": "#ivs_content p",
    "risk_note": "正文按基本信息、现任、历任和分工排列，职务必须限定为当前人物的现任段。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物基本信息段划界并提取其后完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    rows: list[dict] = []
    pending_name = ""
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue

        name_match = re.match(r"^([\u4e00-\u9fff·]{2,8})，(?:男|女)，", text)
        if name_match:
            pending_name = name_match.group(1)
            continue
        if pending_name and re.fullmatch(r"现任[：:].+。", text):
            evidence = re.sub(r"^现任[：:]\s*", "", text).removesuffix("。").strip()
            rows.append(
                {
                    "name": pending_name,
                    "duty": "",
                    "evidence": evidence,
                    "detail_url": "",
                }
            )
            pending_name = ""

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
