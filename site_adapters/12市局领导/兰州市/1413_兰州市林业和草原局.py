from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1413",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_lincao_current_division_notice_strong_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_lincao_current_division_notice_strong_fields_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom strong内姓名（职务）或职级+姓名",
    "duty_selector": "#zoom strong内括号原始职务或姓名前职级",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "current_division_notice_contains_responsibilities_after_explicit_strong_name_duty_fields",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "field_selector": "strong",
        },
        "api": {
            "enabled": False,
            "reason": "当前2025年12月11日领导分工通知正文用strong明确标注10个人物姓名和职务",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def clean_evidence(text: str) -> str:
    """删除已拆分职务中的无期限独立状态标记。"""
    cleaned = re.sub(
        r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])",
        "",
        normalize_space(text),
    )
    return re.sub(r"[，,、；;：:]\s*$", "", cleaned).strip()


def split_field(text: str) -> tuple[str, str]:
    """解析姓名在前的括号职务或职级在前的姓名字段。"""
    normalized = normalize_space(text)
    parenthesized = re.fullmatch(
        r"(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^（）]{2,100})）(?P<extra>（兼）)?",
        normalized,
    )
    if parenthesized is not None:
        return (
            parenthesized.group("name"),
            normalize_space(parenthesized.group("duty") + (parenthesized.group("extra") or "")),
        )

    title_first = re.fullmatch(
        r"(?P<duty>[一二三四五六七八九十]+级调研员)(?P<name>[\u4e00-\u9fff·]{2,4}?)(?:同志)?",
        normalized,
    )
    if title_first is not None:
        return title_first.group("name"), title_first.group("duty")
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按通知正文strong顺序提取明确姓名和原始职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for field in container.select("strong"):
        evidence = normalize_space(field.get_text(" ", strip=True))
        name, duty = split_field(evidence)
        duty = clean_evidence(duty)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty
            or name in seen_names
        ):
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#zoom领导分工通知内strong字段；解析姓名（职务）（兼）或职级+姓名；冒号后职责不纳入",
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
