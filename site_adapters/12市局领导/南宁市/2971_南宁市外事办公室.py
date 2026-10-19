from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2971",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_foreign_affairs_profile_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_foreign_affairs_profile_blocks_v2",
    "leader_region_selector": ".content",
    "name_selector": "分工标签之前最近的姓名独立段",
    "duty_selector": "同一人物块完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "每个人物块依次为姓名、分工标签、职责、现任句；必须在块内配对，不能跨到下一人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".content", "name_selector": "姓名独立段", "duty_selector": "同块完整现任句"}, "api": {"enabled": False, "reason": "静态合并正文逐人提供姓名、分工及现任句"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    current_name = ""
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        compact = text.replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", compact):
            current_name = compact
            continue
        evidence_match = re.fullmatch(r"现任[^。]*。", text)
        if evidence_match is None or not current_name or current_name in seen:
            continue
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            text,
        ).strip()
        seen.add(current_name)
        rows.append({"name": current_name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".content人物块按DOM顺序；姓名独立段与其后同块完整现任句配对"})
        current_name = ""
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
