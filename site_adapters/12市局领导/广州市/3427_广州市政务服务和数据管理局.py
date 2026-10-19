from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3427", "page_type": "人物表格页", "structure_group": "姓名职务职责分工连续强文本段落",
    "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content", "name_selector": "p strong", "duty_selector": "p strong",
    "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".article-content"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文按姓名、职务、职责分工三段重复，必须只取前两段并排除职责段", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序解析姓名、职务和职责分工连续三段中的前两段。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []
    paragraphs = [p for p in article.select("p") if compact_text(p.get_text(" ", strip=True))]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, paragraph in enumerate(paragraphs[:-2]):
        name = compact_text(paragraph.get_text(" ", strip=True))
        if paragraph.select_one("strong") is None or re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None:
            continue
        duty_paragraph = paragraphs[index + 1]
        duty = compact_text(duty_paragraph.get_text(" ", strip=True)).strip("，,。；;")
        division = compact_text(paragraphs[index + 2].get_text(" ", strip=True))
        if duty_paragraph.select_one("strong") is None or not duty or not division.startswith("职责分工：") or name in seen:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": ".article-content姓名强文本段及下一职务强文本段"})
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
