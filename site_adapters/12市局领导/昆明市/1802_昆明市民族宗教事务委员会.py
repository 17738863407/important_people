from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1802",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_ethnic_religious_team_strong_titles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_ethnic_religious_team_strong_titles_v1",
    "leader_region_selector": ".activity",
    "name_selector": "strong职务姓名同志标题中的姓名",
    "duty_selector": "strong职务姓名同志完整标题",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "team_profiles_and_work_divisions_in_one_article",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "headings": "strong",
            "heading_pattern": "职务+姓名+同志",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文以strong标题直接标明班子成员职务和姓名",
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
    """按正文strong标题顺序提取班子成员，排除简历和分工文本。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for strong in region.select("strong"):
        text = normalize_space(strong.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>党组书记、主任|党组成员、副主任)(?P<name>[\u4e00-\u9fff·]{2,4})同志",
            text,
        )
        if not match:
            continue
        name = match.group("name")
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": text,
                "evidence": text,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity；职务姓名同志strong标题",
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
