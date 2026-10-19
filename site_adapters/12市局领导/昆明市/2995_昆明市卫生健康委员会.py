from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2995",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_health_work_division_paragraph_headings_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_health_work_division_headings_v2",
    "leader_region_selector": ".activity",
    "name_selector": "第一章节短段落末尾姓名",
    "duty_selector": "第一章节短段落中姓名前原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "同页包含工作分工、协作关系及可能滞后的领导简历；只解析“领导成员工作分工”至“领导分工协作关系”之间的短职务姓名段落。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "headings": "strong",
            "start_anchor": "一、领导成员工作分工",
            "end_anchor": "二、领导分工协作关系",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML第一章节以strong标题直接标明领导职务和姓名",
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


def parse_heading(text: str) -> tuple[str, str]:
    """解析“以书记、主任或组长结尾的职务+姓名”标题。"""
    compact = re.sub(r"\s+", "", text)
    match = re.fullmatch(
        r"(?P<duty>.*?(?:书记|主任|组长))(?P<name>[\u4e00-\u9fff·]{2,4})",
        compact,
    )
    if not match:
        return "", ""
    return match.group("name"), match.group("duty")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅在第一章节内按strong标题顺序提取领导。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    in_leaders = False
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        if "领导成员工作分工" in text:
            in_leaders = True
            continue
        if "二、" in text and "领导分工协作关系" in text:
            break
        if not in_leaders:
            continue
        name, duty = parse_heading(text)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity第一章节；短段落中的职务姓名标题；排除协作关系与领导简历",
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
