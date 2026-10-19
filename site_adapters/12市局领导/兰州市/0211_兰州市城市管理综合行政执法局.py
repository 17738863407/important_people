from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0211",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_cgzfj_member_division_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_cgzfj_member_division_paragraphs_v1",
    "leader_region_selector": "div#zoom",
    "name_selector": "p > strong",
    "duty_selector": "姓名段后首个非空p的职责说明前原始职务短语",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "duty_and_responsibility_share_one_paragraph",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div#zoom",
            "paragraph_selector": "p",
            "name_marker_selector": ":scope > strong",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文直接包含按人物顺序排列的姓名与职务分工段落",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def is_name_paragraph(paragraph) -> bool:
    """姓名段必须仅由一个直属加粗节点构成。"""
    strong = paragraph.find("strong", recursive=False)
    if strong is None:
        return False
    name = re.sub(r"\s+", "", normalize_space(paragraph.get_text(" ", strip=True)))
    strong_text = re.sub(r"\s+", "", normalize_space(strong.get_text(" ", strip=True)))
    return name == strong_text and bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name))


def extract_original_duty(text: str) -> str:
    """去除同段中从首个职责性逗号开始的分工说明。"""
    return normalize_space(re.split(r"[，。]", normalize_space(text), maxsplit=1)[0])


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取姓名及紧随其后的原始职务短语。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div#zoom")
    if container is None:
        return []

    paragraphs = container.select("p")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for index, paragraph in enumerate(paragraphs):
        if not is_name_paragraph(paragraph):
            continue
        name = re.sub(r"\s+", "", normalize_space(paragraph.get_text(" ", strip=True)))
        if name in seen_names:
            continue
        duty = ""
        for candidate in paragraphs[index + 1 :]:
            if is_name_paragraph(candidate):
                break
            candidate_text = normalize_space(candidate.get_text(" ", strip=True))
            if candidate_text:
                duty = extract_original_duty(candidate_text)
                break
        if not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "div#zoom内仅含直属strong的姓名p；取其后首个非空p在职责说明前的原始职务短语",
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
