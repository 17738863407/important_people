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
    "rule_id": "2023",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_energy_portrait_adjacent_text",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_energy_portrait_adjacent_text_v1",
    "leader_region_selector": ".lzy-scroll-wrap .trs_editor_view",
    "name_selector": "人物头像后第一个非空p",
    "duty_selector": "人物头像后第二个非空p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "附件下载",
        "include_selectors": [".lzy-scroll-wrap .trs_editor_view > p"],
        "exclude_selectors": [".public-annex-downLoad", "网站导航", "联系方式", "页脚"],
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
    "risk_flag": "头像仅作人物块锚点；姓名和职务均由相邻HTML文本提供，不使用OCR，不纳入后续负责分管段落",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".lzy-scroll-wrap .trs_editor_view",
            "name_selector": "人物头像后第一个非空p",
            "duty_selector": "人物头像后第二个非空p",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "附件下载",
                "include_selectors": [".lzy-scroll-wrap .trs_editor_view > p"],
                "exclude_selectors": [".public-annex-downLoad", "网站导航", "联系方式", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML在每张人物头像后直接提供姓名和职务段落"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(
        str(value or "")
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .replace("\u2002", " ")
        .replace("\u2003", " ")
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
        if "trs_editor_view" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one(".lzy-scroll-wrap .trs_editor_view")
    if editor is None or _is_hidden(editor):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for portrait_paragraph in editor.find_all("p", recursive=False):
        if portrait_paragraph.find("img") is None or _is_hidden(portrait_paragraph):
            continue
        following_texts: list[str] = []
        for paragraph in portrait_paragraph.find_next_siblings("p"):
            if paragraph.find("img") is not None:
                break
            text = _clean_text(paragraph.get_text(" ", strip=True))
            if text:
                following_texts.append(text)
            if len(following_texts) == 2:
                break
        if len(following_texts) < 2:
            continue
        name = re.sub(r"\s+", "", following_texts[0])
        duty = following_texts[1].strip(" ：:，,。.；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_energy_portrait_adjacent_text_v1",
                "selector_summary": ".lzy-scroll-wrap头像p；后续首个非空p姓名；第二个非空p职务",
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
