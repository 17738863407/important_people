from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4338",
    "page_type": "现任领导单页简介",
    "structure_group": "snai_centered_name_duty_pairs_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_snai_current_leaders_v1",
    "leader_region_selector": ".v_news_content, .wp_articlecontent",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务为相邻居中段落；后续长段落为简历，不参与职务抽取。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "adjacent_centered_paragraphs",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文顺序提取相邻的姓名段落与学院职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        paragraph_text = " ".join(paragraph.get_text(" ", strip=True).split())
        same_line = re.fullmatch(r"([\u3400-\u9fff·]{2,6})\s+(上海国家会计学院.{1,70})", paragraph_text)
        if same_line:
            rows.append({"name": same_line.group(1), "duty": same_line.group(2), "detail_url": ""})
            continue
        name = re.sub(r"\s+", "", paragraph_text)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        next_paragraph = paragraph.find_next_sibling("p")
        duty = " ".join(next_paragraph.get_text(" ", strip=True).split()) if next_paragraph else ""
        if duty.startswith("上海国家会计学院") and len(duty) <= 80:
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导正文未解析到相邻的姓名与学院职务段落")
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
