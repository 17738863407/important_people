from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3368",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_housing_zoom_name_parenthesized_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_housing_zoom_name_parenthesized_duty_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p段首姓名（职务）：中姓名",
    "duty_selector": "#zoom p段首姓名（职务）：中括号原字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "duty_lines_share_paragraphs_with_long_responsibility_text",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoom", "row_selector": "#zoom p"},
        "api": {"enabled": False, "reason": "当前在线#zoom直出7个段首姓名（职务）：强结构段落"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#zoom段落顺序提取段首姓名（职务）：原字段。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in container.find_all("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})\s*（(?P<duty>[^（）]{2,100})）：", text)
        if not match:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        if name in seen:
            continue
        seen.add(name)
        # 括号内字段是当前人物可回指的原始职务；姓名和冒号均为列表排版，不写入依据说明。
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#zoom正文p按DOM顺序；仅接受段首姓名（职务）：强结构字段"})
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
