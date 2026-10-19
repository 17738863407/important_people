from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2589",
    "page_type": "人物表格页",
    "structure_group": "姓名段落与相邻职务标记段落",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "地址：",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文含简介与分管说明，仅接受姓名段落后紧邻的职务标记段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    """移除姓名和职务中的网页排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析姓名及其下一非空职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []

    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in article.select("p")
        if paragraph.get_text(" ", strip=True)
    ]
    name_pattern = re.compile(r"^[\u4e00-\u9fff·\s]{2,8}$")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, value in enumerate(paragraphs[:-1]):
        if name_pattern.fullmatch(value) is None:
            continue
        duty_match = re.fullmatch(r"职务\s*[：:]\s*(.+)", paragraphs[index + 1])
        if duty_match is None:
            continue
        name = compact_text(value)
        duty = compact_text(duty_match.group(1)).strip("，,。；;")
        if not duty or name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article-content姓名段落及下一非空职务标记段落",
            }
        )
        seen.add(name)

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
