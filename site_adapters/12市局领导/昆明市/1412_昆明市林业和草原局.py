from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1412",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_forestry_merged_strong_headings_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_forestry_merged_strong_headings_v1",
    "leader_region_selector": ".right .content .activity",
    "name_selector": "人物strong标题末尾姓名",
    "duty_selector": "人物strong标题中姓名前的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "multiple_people_share_one_entry_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".right .content .activity",
            "headings": "strong",
            "excluded_heading_texts": ["简历", "工作分工"],
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML合并正文直接包含各人物职务姓名标题",
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
    """从多人合并正文的强标题按网页顺序提取人物。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right .content .activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for strong in region.select("strong"):
        text = normalize_space(strong.get_text(" ", strip=True))
        if text in {"简历", "工作分工"}:
            continue
        match = re.match(
            r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,4})$",
            text,
        )
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        if not re.search(r"局长|主任|书记|成员", duty):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".right .content .activity；人物strong职务姓名标题",
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
