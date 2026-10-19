from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2813",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_veterans_merged_profile_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_veterans_merged_profile_paragraphs_v1",
    "leader_region_selector": ".activity",
    "name_selector": "简历内容段开头至首个逗号",
    "duty_selector": "同一简历内容段完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "profiles_and_work_divisions_in_same_article",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "paragraphs": "p",
            "profile_pattern": "段首姓名+履历+完整现任句",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML合并正文以独立段落直接包含姓名、履历和现任句",
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
    """仅解析包含段首姓名和现任句的简历内容段。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[，,]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        if name in seen_names:
            continue
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).rstrip("。")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity；段首姓名简历段；同段完整现任句",
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
