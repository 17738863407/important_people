from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1395",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_audit_work_division_titles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_audit_work_division_titles_v1",
    "leader_region_selector": "#detail_con",
    "name_selector": "含同志标题段中的职务后姓名",
    "duty_selector": "含同志的完整标题段",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "work_division_title_then_responsibility_paragraphs",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#detail_con",
            "title_paragraphs": "p containing 同志 before 分工互补协作关系",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接包含领导职务姓名标题段",
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


def parse_title(text: str) -> tuple[str, str]:
    """解析“职务 姓名 同志”，保留完整标题作为原文依据。"""
    match = re.match(
        r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s+同志$",
        text,
    )
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
        return "", ""
    return name, match.group("duty").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标题段的网页顺序提取领导，排除后续分工说明。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#detail_con")
    if content is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in content.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        if "分工互补协作关系" in text:
            break
        if "同志" not in text or "——" in text:
            continue
        name, duty = parse_title(text)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": text,
                "evidence": text,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#detail_con；分工说明前含同志标题段；职务后姓名",
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
