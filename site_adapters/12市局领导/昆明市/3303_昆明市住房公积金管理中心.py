from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3303",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_housing_fund_merged_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_housing_fund_merged_profiles_v1",
    "leader_region_selector": ".activity",
    "name_selector": "h3括号前姓名",
    "duty_selector": "同一人物区完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "profile_current_position_and_work_division_share_article",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "titles": "h3",
            "profile_paragraphs": "p",
            "title_pattern": "姓名（职务）",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML合并正文直接包含h3人物标题、简历现任句和工作分工",
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
    """解析h3“姓名（职务）”标题。"""
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,4})[（(](?P<duty>[^）)]+)[）)]", text)
    if not match:
        return "", ""
    return match.group("name"), normalize_space(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """以h3人物标题为边界，提取随后简历段的完整现任句。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    current_name = ""
    current_title_duty = ""
    seen_names: set[str] = set()
    for node in region.find_all(["h3", "p"]):
        text = normalize_space(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name == "h3":
            current_name, current_title_duty = parse_title(text)
            continue
        if not current_name or current_name in seen_names:
            continue
        evidence_match = re.search(r"现任[^。]*。", text)
        if evidence_match is None:
            continue
        evidence = evidence_match.group(0)
        evidence = re.sub(r"^现任", "", evidence).rstrip("。")
        seen_names.add(current_name)
        rows.append(
            {
                "name": current_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": f".activity；h3姓名职务标题；同区现任句；标题职务={current_title_duty}",
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
