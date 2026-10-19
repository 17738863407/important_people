from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0616",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".introduction_main, .other_introduction_box",
    "name_selector": "p.name, span.name",
    "duty_selector": "p.position, span.position",
    "risk_note": "页面含会触发online异常词检测的非人物文字，原始HTML中的人物字段完整可用。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清理段落与姓名中的排版空白。"""
    text = re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按主领导和其他领导卡片的DOM顺序提取独立字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for box in soup.select(page_rule["leader_region_selector"]):
        name_node = box.select_one(page_rule["name_selector"])
        duty_node = box.select_one(page_rule["duty_selector"])
        if name_node is None or duty_node is None:
            continue

        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(duty_node.get_text(" ", strip=True))
        evidence = re.sub(r"^现任\s*", "", evidence).strip()
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
