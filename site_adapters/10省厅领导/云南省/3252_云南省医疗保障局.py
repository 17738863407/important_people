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
    "rule_id": "3252",
    "page_type": "多人物详情合并页",
    "structure_group": "yunnan_medical_portrait_profile_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_medical_portrait_profile_blocks_v2",
    "leader_region_selector": "div.body #infoyh",
    "name_selector": "头像块内简历段首个逗号前文本",
    "duty_selector": "头像块内简历段完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首张人物头像",
        "end_anchor": "末个人物分工段",
        "include_selectors": ["div.body #infoyh > p"],
        "exclude_selectors": ["分工段", "pageLink", "导航", "页脚"],
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
    "risk_flag": "每个人物块含简历和分工；只在当前头像至下一头像之间的简历段提取完整现任句，分工不作主职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.body #infoyh",
            "name_selector": "头像块内简历段首个逗号前文本",
            "duty_selector": "头像块内简历段完整现任句",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首张人物头像",
                "end_anchor": "末个人物分工段",
                "include_selectors": ["div.body #infoyh > p"],
                "exclude_selectors": ["分工段", "pageLink", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML人物块直接提供姓名和完整现任句"},
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
        if str(current.get("id", "")) == "infoyh":
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.body #infoyh")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for portrait_paragraph in region.find_all("p", recursive=False):
        if portrait_paragraph.find("img") is None or _is_hidden(portrait_paragraph):
            continue
        profile = ""
        for paragraph in portrait_paragraph.find_next_siblings("p"):
            if paragraph.find("img") is not None:
                break
            text = _clean_text(paragraph.get_text(" ", strip=True))
            if "现任" in text:
                profile = text
                break
        if not profile:
            continue
        match = re.search(
            r"(?:简历[：:]\s*)?(?P<name>[\u4e00-\u9fff·.]{2,20})[，,].*?(?P<evidence>现任[^。]*。)",
            profile,
        )
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("evidence").removeprefix("现任").removesuffix("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "parser": "custom_yunnan_medical_portrait_profile_blocks_v2",
                "selector_summary": "div.body #infoyh头像p；同一块简历段姓名与完整现任句",
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
