from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2730",
    "domain": "tjj.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "scoped_strong_name_role_sequence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_html",
    "parser": "page_inline_scoped_strong_name_role_sequence_v1",
    "leader_region_selector": "#zoom",
    "header_selector": "strong",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "一名人物姓名与职务分列相邻加粗节点；正文另含简历和分管职责",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩正文中的排版空白，不改变原始职务文本。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def extract_name(node: Tag) -> str:
    """从加粗标题的独立文本片段取得姓名。"""
    for value in node.find_all(string=True):
        text = re.sub(r"\s+", "", clean_text(value))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", text):
            return text
    return ""


def extract_duty(node: Tag) -> str:
    """从加粗标题中选择最小的完整职务文本节点。"""
    candidates = [clean_text(item.get_text(" ", strip=True)) for item in node.select("span")]
    candidates.append(clean_text(node.get_text(" ", strip=True)))
    role_candidates = [
        text
        for text in candidates
        if text
        and any(keyword in text for keyword in ("党组", "局长", "巡视员"))
        and not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", text)
    ]
    return min(role_candidates, key=len) if role_candidates else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按#zoom加粗标题的DOM顺序配对姓名和原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    pending_name = ""
    for node in region.select(str(page_rule.get("header_selector", "strong"))):
        if not clean_text(node.get_text(" ", strip=True)):
            continue
        name = extract_name(node)
        duty = extract_duty(node)
        if name:
            pending_name = name
        if not pending_name or not duty or pending_name in seen:
            continue

        seen.add(pending_name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": pending_name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=#zoom；header=strong DOM sequence；"
                    "name=independent Han text；duty=smallest role span；adjacent split supported"
                ),
            }
        )
        pending_name = ""

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
