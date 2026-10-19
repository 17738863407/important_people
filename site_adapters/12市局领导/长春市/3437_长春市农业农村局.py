from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3437",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_agriculture_name_duty_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_agriculture_name_duty_paragraphs_v1",
    "leader_region_selector": ".zlyxwz_t2a p",
    "name_selector": "职务标题段开头姓名",
    "duty_selector": "同一标题段姓名后的完整职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".zlyxwz_t2a"],
        "exclude_selectors": ["iframe", "script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名职务标题与历任、主持、分管段落交错；仅解析完整匹配的标题段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_strong_name_duty_paragraph",
    "locator": {
        "css": {
            "leader_region_selector": ".zlyxwz_t2a p",
            "name_selector": "paragraph_start_name",
            "duty_selector": "same_paragraph_verified_duty",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "原始HTML正文使用独立段落直接提供姓名和职务"},
        "migration": {
            "source": "legacy_paragraph_regex",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_DUTY_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fff]{2,4})"
    r"(?P<duty>(?:长春市农业农村局)?(?:党组书记|党组成员、副局长(?:（正局长级）)?|二级巡视员))"
)


def compact_text(text: str) -> str:
    """仅清理HTML排版空白，不改写职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取完整匹配的姓名职务标题。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        text = compact_text(paragraph.get_text(" ", strip=True))
        match = NAME_DUTY_PATTERN.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "source_text": duty,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=leader_content_paragraphs；heading=fullmatch；resume_and_division=excluded",
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
