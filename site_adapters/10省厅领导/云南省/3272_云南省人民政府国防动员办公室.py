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
    "rule_id": "3272",
    "page_type": "职务分组名单页",
    "structure_group": "yunnan_defense_duty_responsibility_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_defense_duty_responsibility_paragraphs_v2",
    "leader_region_selector": ".mart",
    "name_selector": ".mart p冒号前党组字段之前文本",
    "duty_selector": ".mart p冒号前党组字段起始文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个人物职责段",
        "end_anchor": "末个人物职责段",
        "include_selectors": [".mart > p"],
        "exclude_selectors": ["冒号后职责", "落款", "日期", "导航", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "人物段冒号后为主持、协助和负责事项；只保留冒号前姓名及党组职务，排除职责、落款和日期",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".mart",
            "name_selector": "p冒号前党组字段之前文本",
            "duty_selector": "p冒号前党组字段起始文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个人物职责段",
                "end_anchor": "末个人物职责段",
                "include_selectors": [".mart > p"],
                "exclude_selectors": ["冒号后职责", "落款", "日期", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML人物段直接提供姓名、职务和职责分隔结构"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(
        str(value or "")
        .replace("\u2002", " ")
        .replace("\u2003", " ")
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .split()
    )


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "mart" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".mart")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.find_all("p", recursive=False):
        if _is_hidden(paragraph):
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True)).replace(":", "：")
        if "：" not in text:
            continue
        head = text.split("：", 1)[0]
        compact_head = re.sub(r"\s+", "", head)
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·.]{2,20}?)(?P<duty>党组.+)", compact_head)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty").strip(" ：:，,。.；;")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_defense_duty_responsibility_paragraphs_v2",
                "selector_summary": ".mart直接p；冒号前党组字段前姓名；党组字段起职务",
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
