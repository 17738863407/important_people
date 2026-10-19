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
    "rule_id": "3236",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_research_office_static_leader_division_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "custom_yunnan_research_office_leader_division_paragraphs_v3",
    "leader_region_selector": ".lzy-scroll-wrap",
    "name_selector": "人物职务p中党组字段之前文本",
    "duty_selector": "人物职务p中党组字段起始文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "云南省人民政府研究室领导班子成员工作分工",
        "end_anchor": "AB角说明之前",
        "include_selectors": [".lzy-scroll-wrap > p"],
        "exclude_selectors": ["主持", "分管", "AB角", "互动频道", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "静态正文含独立职责段和AB角说明，人物姓名存在字距空格；只接受正文直接子段中姓名后紧接党组职务的完整结构",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-scroll-wrap",
            "name_selector": "人物职务p中党组字段之前文本",
            "duty_selector": "人物职务p中党组字段起始文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "云南省人民政府研究室领导班子成员工作分工",
                "end_anchor": "AB角说明之前",
                "include_selectors": [".lzy-scroll-wrap > p"],
                "exclude_selectors": ["主持", "分管", "AB角", "互动频道", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前原始HTML正文直接提供姓名和职务，无需额外接口或浏览器渲染"},
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
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".lzy-scroll-wrap")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.find_all("p", recursive=False):
        if _is_hidden(paragraph):
            continue
        compact = re.sub(r"\s+", "", _clean_text(paragraph.get_text(" ", strip=True)))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·.]{2,20})(?P<duty>党组[^。；]{2,60})", compact)
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
                "parser": "custom_yunnan_research_office_leader_division_paragraphs_v3",
                "selector_summary": "领导信息正文直接p；党组字段前姓名；党组字段起始职务",
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
