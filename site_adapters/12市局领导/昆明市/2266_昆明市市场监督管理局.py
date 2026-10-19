from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2266",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_market_supervision_merged_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_market_supervision_merged_profiles_v1",
    "leader_region_selector": ".activity",
    "name_selector": "人物区段首独立姓名段落",
    "duty_selector": "紧随姓名的简历/简介段内现任原句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "multiple_profiles_with_phone_and_responsibility_text",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "paragraphs": "p",
            "name_paragraph": "standalone Chinese name",
            "evidence_paragraph": "following 简历 or 简介 paragraph",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML合并正文直接包含姓名、简介现任句、电话和岗位职责",
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


def compact_name(text: str) -> str:
    """清除姓名内部由版式产生的空格。"""
    return re.sub(r"\s+", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """以独立姓名段为边界，仅读取相邻简介中的现任原句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    current_name = ""
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        possible_name = compact_name(text)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", possible_name):
            current_name = possible_name
            continue
        if not current_name or current_name in seen_names:
            continue
        if not text.startswith(("简历：", "简介：")) or current_name not in compact_name(text):
            continue
        evidence_match = re.search(r"现任[^。]*(?:。|$)", text)
        if evidence_match is None:
            continue
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            evidence_match.group(0).strip(),
        ).rstrip("。；; ")
        if not evidence:
            continue
        seen_names.add(current_name)
        rows.append(
            {
                "name": current_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity；独立姓名段；相邻简历/简介段现任原句",
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
