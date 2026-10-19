from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3308",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_housing_construction_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_housing_construction_profiles_v1",
    "leader_region_selector": ".activity",
    "name_selector": "人物职务标题末尾姓名",
    "duty_selector": "同一人物简历段完整至今任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "current_sentence_may_differ_from_heading_and_history_is_mixed_in_profile",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "paragraphs": "p",
            "title_pattern": "职务+空格+姓名",
            "evidence_pattern": "同一人物区完整至今任句",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接包含人物标题、履历、至今任当前句和工作分工",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不添加机构前缀。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_title(text: str) -> tuple[str, str]:
    """解析限定职务开头的“职务 姓名”人物标题。"""
    match = re.fullmatch(
        r"(?P<duty>(?:党组.+?|副局长))\s+(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})",
        text,
    )
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
        return "", ""
    return name, match.group("duty").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """直接提取人物标题中与姓名一一对应的职务元素。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        name, title_duty = parse_title(text)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": title_duty,
                "evidence": title_duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity；人物职务姓名标题；姓名前职务元素",
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
