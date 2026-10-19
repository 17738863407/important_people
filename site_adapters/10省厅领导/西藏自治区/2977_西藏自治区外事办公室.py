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
    "rule_id": "2977",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_foreign_affairs_name_duty_paragraph_pairs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "page_inline",
    "collector": "static_http",
    "parser": "custom_xizang_foreign_affairs_name_duty_pairs_v1",
    "leader_region_selector": ".TRS_UEDITOR",
    "name_selector": ".TRS_UEDITOR > p strong",
    "duty_selector": "姓名段后的首个非空p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个strong姓名段",
        "end_anchor": "末个职务段",
        "include_selectors": [".TRS_UEDITOR > p"],
        "exclude_selectors": ["空段"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名与职务分属相邻段落；只接受strong姓名段及其后首个以自治区外事办公室开头的非空段，禁止全页扫描",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".TRS_UEDITOR",
            "name_selector": "> p strong",
            "duty_selector": "姓名p之后首个非空p",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个姓名段",
                "end_anchor": "末个职务段",
                "include_selectors": [".TRS_UEDITOR > p"],
                "exclude_selectors": ["空段"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接提供相邻姓名与职务段",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(text.split())


def _next_nonempty_paragraph(paragraph: object) -> str:
    current = paragraph.find_next_sibling("p")
    while current is not None:
        text = _clean_text(current.get_text(" ", strip=True))
        if text:
            return text
        current = current.find_next_sibling("p")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文DOM顺序配对strong姓名段和其后首个非空职务段。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_UEDITOR")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select(":scope > p"):
        name_node = paragraph.select_one("strong")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        duty = _next_nonempty_paragraph(paragraph)
        duty = duty.strip(" ，,。；;：: ")
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name)
            or not duty.startswith("自治区外事办公室")
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_xizang_foreign_affairs_name_duty_pairs_v1",
                "selector_summary": ".TRS_UEDITOR；strong姓名段；后续首个非空职务段",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
