from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1458",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".government-detail-r-items",
    "item_selector": ".government-detail-r-items .government-detail-ite",
    "name_selector": ".government-detail-ite-img span",
    "risk_note": "人物块同时含现任职务、履历和分工，只读取“现任职务”标题的相邻段落。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def clean_evidence(value: str) -> str:
    """删除职务字段的纯句末句号。"""
    text = clean_text(value)
    return text[:-1].rstrip() if text.endswith("。") else text


def find_current_duty(block) -> str:
    """查找当前人物块中“现任职务”标题紧邻的原文段落。"""
    for title in block.select(".government-detail-ite-text h4"):
        if clean_text(title.get_text(" ", strip=True)) != "现任职务":
            continue
        paragraph = title.find_next_sibling("p")
        return clean_evidence(paragraph.get_text(" ", strip=True)) if paragraph else ""
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物块DOM顺序提取独立姓名和现任职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for block in soup.select(page_rule["item_selector"]):
        name_node = block.select_one(page_rule["name_selector"])
        if name_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = find_current_duty(block)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
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
