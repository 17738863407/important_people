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
    "rule_id": "0473",
    "page_type": "职务分组名单页",
    "structure_group": "changchun_drc_current_heading_before_hr_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_drc_current_heading_before_hr_v1",
    "leader_region_selector": "div.TRS_Editor直属p，截止首个hr",
    "name_selector": "冒号前标题的开头姓名",
    "duty_selector": "冒号前标题中姓名后的原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "首个hr",
        "include_selectors": ["div.TRS_Editor"],
        "exclude_selectors": ["iframe"],
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
    "risk_flag": "首个hr之后包含领导简历、历史任职、联系电话和审校人员，必须硬边界排除",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_current_heading_before_hr",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor direct_children_before_first_hr",
            "name_selector": "heading_prefix_name",
            "duty_selector": "heading_before_colon_after_name",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文首段组已直接给出现任姓名、职务及分工",
        },
        "migration": {
            "source": "legacy_inline_current_section_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


HEADING_PATTERN = re.compile(
    r"^(?P<name>[\u4e00-\u9fff]\s*[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){0,2})\s+"
    r"(?P<duty>.+)$"
)
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def split_current_heading(paragraph: str) -> tuple[str, str]:
    """从冒号前人物标题拆分姓名和原始职务。"""
    normalized = clean_text(paragraph)
    head = re.split(r"[：:]", normalized, maxsplit=1)[0]
    match = HEADING_PATTERN.fullmatch(head)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    evidence = re.sub(r"\s+", "", match.group("duty"))
    if NAME_PATTERN.fullmatch(name) is None or DUTY_HINT_PATTERN.search(evidence) is None:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只解析正文首个hr之前的现任负责人标题。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one("div.TRS_Editor")
    if editor is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in editor.children:
        if getattr(node, "name", None) == "hr":
            break
        if getattr(node, "name", None) != "p":
            continue
        paragraph = clean_text(node.get_text(" ", strip=True))
        if "：" not in paragraph and ":" not in paragraph:
            continue
        name, evidence = split_current_heading(paragraph)
        if not name or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=TRS_Editor_before_first_hr；"
                    "name=heading_prefix；duty=heading_before_colon_after_name；"
                    "responsibility_history_and_reviewers=excluded"
                ),
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
