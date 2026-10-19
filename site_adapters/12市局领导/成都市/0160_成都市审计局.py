from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0160",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#container",
    "item_selector": "p.MsoNormal, p.p, .article p, .TRS_Editor p",
    "risk_note": "HTTP请求返回412，需浏览器采集；正文按姓名、领导职务标题、职务值重复排列。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清除正文编辑器产生的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按段落序列提取姓名及领导职务标题后的独立职务段。"""
    soup = BeautifulSoup(html, "html.parser")
    texts = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(page_rule["item_selector"])]
    texts = [text for text in texts if text]
    rows: list[dict] = []
    current_name = ""

    for index, text in enumerate(texts):
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", text) and text not in {
            "领导介绍",
            "领导职务",
            "领导分工",
            "领导简历",
        }:
            current_name = text
            continue
        if not current_name or not text.startswith("领导职务"):
            continue
        evidence = ""
        for candidate in texts[index + 1 : index + 4]:
            if candidate.startswith(("领导职务", "领导分工", "领导简历")):
                break
            evidence = candidate.strip("：:；;。 ")
            if evidence:
                break
        if not evidence:
            continue
        rows.append(
            {
                "name": current_name,
                "duty": "",
                "evidence": evidence,
                "detail_url": "",
            }
        )
        current_name = ""

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
