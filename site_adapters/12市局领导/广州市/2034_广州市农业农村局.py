from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2034",
    "page_type": "人物表格页",
    "structure_group": "人物标题段落姓名与机构职务连续文本",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content p",
    "name_selector": "strong",
    "duty_selector": "strong",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名和职务分布于同一段落的多个嵌套strong节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    """移除网页排版空白，保留职务原有标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序解析人物标题段落中的姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    title_pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff·]{2,4}?)"
        r"(?P<duty>(?:中共广州市委|广州市农业农村局).+)$"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".article-content p"):
        if paragraph.select_one("strong") is None:
            continue
        text = compact_text(paragraph.get_text(" ", strip=True)).strip("，,。；;：:")
        match = title_pattern.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article-content人物标题段落内姓名及机构起始职务",
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
