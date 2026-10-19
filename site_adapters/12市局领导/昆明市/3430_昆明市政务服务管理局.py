from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3430",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_gov_service_strong_headings_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_gov_service_strong_headings_v1",
    "leader_region_selector": ".article_content",
    "name_selector": "p:has(strong)标题段末尾姓名",
    "duty_selector": "p > strong原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "shared_article_contains_biographies_and_work_divisions",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "region": ".article_content",
            "headings": "p:has(strong)",
            "duty": "strong",
            "name": "normalized heading suffix",
        },
        "api": {
            "enabled": False,
            "reason": "文章正文中的强标题段已直接给出人物姓名与职务",
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文强标题段顺序提取人物姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".article_content")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        duty = normalize_space(strong.get_text(" ", strip=True)).rstrip("，,；;。")
        heading = normalize_space(paragraph.get_text(" ", strip=True))
        if not duty or not heading.startswith(duty):
            continue
        name = re.sub(r"\s+", "", heading[len(duty) :])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".article_content人物strong标题段",
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
