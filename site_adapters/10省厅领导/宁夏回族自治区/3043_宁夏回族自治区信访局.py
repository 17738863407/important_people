from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3043",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".view.TRS_UEDITOR",
    "row_selector": ".view.TRS_UEDITOR > p",
    "name_selector": "◆职务标题段冒号后姓名",
    "duty_selector": "紧随标题的本人简介首句现职",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "正文还含分工与AB岗说明；必须以◆标题定人，仅在紧随标题的本人简介首句提取完整现职。",
}


def normalize_text(text: str) -> str:
    """仅压缩段落中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按◆职务标题与紧邻本人简介的DOM顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".view.TRS_UEDITOR")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    paragraphs = region.select(":scope > p")
    for index, paragraph in enumerate(paragraphs):
        heading = normalize_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"◆\s*[^：:]{1,20}[：:]\s*([\u4e00-\u9fff·]{2,5})", heading)
        if match is None:
            continue
        name = match.group(1)

        intro = ""
        for candidate in paragraphs[index + 1 :]:
            candidate_text = normalize_text(candidate.get_text(" ", strip=True))
            if candidate_text:
                intro = candidate_text
                break
        duty_match = re.search(rf"{re.escape(name)}，[^。]*?，(?P<duty>自治区[^。]*?信访局[^。]*?)。", intro)
        if duty_match is None:
            continue
        duty = normalize_text(duty_match.group("duty"))
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty})

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
