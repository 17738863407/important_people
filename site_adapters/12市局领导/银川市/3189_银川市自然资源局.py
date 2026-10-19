from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3189", "page_type": "多人物详情合并页", "structure_group": "yinchuan_natural_resources_titled_blocks_v2", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_yinchuan_natural_resources_titled_blocks_v2",
    "leader_region_selector": ".zwxxgk_bd", "name_selector": "叶级人物标题段括号前姓名", "duty_selector": "当前人物块现任行或标题括号职务", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zwxxgk_bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "各人物由标题、简介、现任行和工作分工组成；优先取当前块现任原行，无现任行时取标题括号职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

TITLE_PATTERN = re.compile(r"^([\u4e00-\u9fff·\s]{2,8})\s*[（(]\s*([^）)]+?)\s*[）)]$")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物标题划分正文块，优先提取同块现任原行。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in region.select("p") if node.select_one("p") is None]
    paragraphs = [text for text in paragraphs if text]
    headers: list[tuple[int, re.Match[str]]] = []
    for index, text in enumerate(paragraphs):
        match = TITLE_PATTERN.fullmatch(text)
        if match is not None:
            headers.append((index, match))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for order, (start, match) in enumerate(headers):
        end = headers[order + 1][0] if order + 1 < len(headers) else len(paragraphs)
        name = "".join(match.group(1).split())
        heading_duty = _clean_text(match.group(2))
        present_line = next((text for text in paragraphs[start + 1 : end] if re.match(r"^现\s*任", text)), "")
        evidence = (present_line or heading_duty).removeprefix("现任").strip().removesuffix("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": ".zwxxgk_bd内人物标题块；优先同块现任原行；无现任行则标题括号职务"})
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
