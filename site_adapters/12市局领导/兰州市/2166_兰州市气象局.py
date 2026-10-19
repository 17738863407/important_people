from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2166",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_meteorology_duty_name_division_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_meteorology_duty_name_division_paragraphs_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p冒号前职务后姓名",
    "duty_selector": "#zoom p冒号前姓名前原始职务及挂职标记",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "duty_and_name_are_concatenated_before_colon_and_responsibilities_follow",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "paragraph_selector": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文7个段落均以明确职务+姓名+冒号开头，后接分工说明",
        },
    },
}


HEADING_PATTERN = re.compile(
    r"^(?P<duty>党组书记、局长|党组成员、纪检组组长|党组成员、副局长|[一二三四五六七八九十]+级调研员)"
    r"(?P<name>[\u4e00-\u9fff·]{2,8})(?P<extra>（挂职）)?$"
)


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析冒号前明确职务、姓名及挂职标记。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in container.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        heading = text.split("：", 1)[0] if "：" in text else ""
        match = HEADING_PATTERN.fullmatch(heading)
        if match is None:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
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
                "selector_summary": "#zoom领导分工段落；冒号前按明确职务边界拆分姓名并保留挂职标记；冒号后职责不纳入",
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
