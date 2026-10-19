from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4006",
    "page_type": "协会负责人分组卡片页",
    "structure_group": "cnccea_leadership_groups",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "online",
    "parser": "custom_cnccea_leadership_groups_v1",
    "leader_region_selector": ".leadership-content",
    "name_selector": ".position-group .leader-card h4",
    "duty_selector": ".position-group .position-title",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "第三届负责人",
        "end_anchor": "主管单位",
        "include_selectors": [".leadership-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名文本可能含网页明确附加现职；须与分组职务合并，并删除纯排序附注。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验三个负责人分组及卡片顺序，页面不提供独立人物详情链接。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leadership-content",
            "group_selector": ".position-group",
            "name_selector": ".leader-card h4",
            "duty_selector": ".position-title",
        },
        "api": {"enabled": False, "reason": "浏览器渲染DOM已完整提供负责人分组"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip()


def clean_group_duty(value: str) -> str:
    """删除仅说明展示顺序的附注，保留真实职务标题。"""
    return re.sub(r"（排名不分先后）$", "", clean_text(value)).strip()


def split_name_and_extra_duties(value: str) -> tuple[str, list[str]]:
    """从姓名后的全角括号中动态拆出网页明确标注的附加现职。"""
    text = clean_text(value)
    match = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})(?:（([^（）]+)）)?", text)
    if match is None:
        return "", []
    extras = [item.strip() for item in re.split(r"[、，,；;]", match.group(2) or "") if item.strip()]
    return match.group(1), extras


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按负责人分组及卡片的原始DOM顺序提取。"""
    del final_url
    root = BeautifulSoup(html, "html.parser").select_one(".leadership-content")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    for group in root.select(".position-group"):
        title = group.select_one(".position-title")
        if title is None:
            continue
        group_duty = clean_group_duty(title.get_text(" ", strip=True))
        if not group_duty:
            continue
        for name_node in group.select(".leader-card h4"):
            name, extra_duties = split_name_and_extra_duties(name_node.get_text(" ", strip=True))
            if not name:
                continue
            duties = list(dict.fromkeys([group_duty, *extra_duties]))
            duty = "；".join(duties)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".position-group 标题及组内 .leader-card h4",
                }
            )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
