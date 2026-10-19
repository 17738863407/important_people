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
    "rule_id": "0500",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_dzys_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_dzys_name_duty_paragraphs_v1",
    "leader_region_selector": ".TRS_Editor p",
    "name_selector": ".TRS_Editor p中U+2002分隔符前",
    "duty_selector": ".TRS_Editor p中U+2002分隔符后首句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息首段",
        "end_anchor": "领导信息末段",
        "include_selectors": [".TRS_Editor p"],
        "exclude_selectors": ["负责分工", "分管联系", "空排版段", "页眉页脚"],
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
    "risk_flag": "正文每段在姓名后使用U+2002分隔，姓名内部可能使用全角空格；职务只取分隔后首个句号前原文",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".TRS_Editor p",
            "name_selector": "U+2002分隔符前并清除姓名内部排版空格",
            "duty_selector": "U+2002分隔符后首句",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息首段",
                "end_anchor": "领导信息末段",
                "include_selectors": [".TRS_Editor p"],
                "exclude_selectors": ["负责分工", "分管联系", "空排版段", "页眉页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文段直接提供姓名、职务和后续分工，页面无人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "trs_editor" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _split_paragraph(raw_text: str) -> tuple[str, str, str]:
    if "\u2002" not in raw_text:
        return "", "", ""
    raw_name, remainder = raw_text.split("\u2002", 1)
    name = re.sub(r"\s+", "", _clean_text(raw_name))
    duty = _clean_text(remainder).split("。", 1)[0].strip()
    evidence = duty
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".TRS_Editor p"):
        if _is_hidden(paragraph):
            continue
        raw_text = paragraph.get_text("", strip=True)
        name, duty, evidence = _split_paragraph(raw_text)
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": evidence,
                "parser": "custom_yunnan_dzys_name_duty_paragraphs_v1",
                "selector_summary": ".TRS_Editor p；U+2002前姓名、后首句职务",
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
