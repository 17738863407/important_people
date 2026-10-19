from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3408",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_natural_resources_merged_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_natural_resources_merged_profiles_v2",
    "leader_region_selector": "#contentText p",
    "name_selector": "人物段开头姓名+性别",
    "duty_selector": "同一人物段完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "正文含词内排版空格及后续分工；仅在同一人物段内清理空白并提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#contentText p",
            "name_selector": "段首姓名+性别",
            "duty_selector": "同段完整现任句",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "合并简介正文由静态HTML直接提供"},
    },
}


def compact_layout(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#contentText")
    if root is None:
        raise RuntimeError("页面缺少#contentText领导正文")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        text = compact_layout(paragraph.get_text(" ", strip=True))
        person_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})(?:男|女)，", text)
        if person_match is None:
            continue
        name = person_match.group("name")
        duty_match = re.search(r"现任[^。]*。", text)
        if duty_match is None:
            raise RuntimeError(f"人物{name}所在段未找到完整现任句")
        if name in seen:
            continue
        evidence = re.sub(r"^现任\s*", "", duty_match.group(0)).rstrip("。").strip()
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#contentText独立人物段按DOM顺序；段首姓名性别与同段完整现任句",
            }
        )
    if not rows:
        raise RuntimeError("领导正文未提取到有效人物段")
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
