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
    "rule_id": "0532",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_housing_name_duty_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_housing_name_duty_fields_v1",
    "leader_region_selector": "#zoom div.TRS_Editor p",
    "name_selector": "姓名字段",
    "duty_selector": "同组紧邻职务字段",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名：",
        "end_anchor": "",
        "include_selectors": ["#zoom div.TRS_Editor"],
        "exclude_selectors": ["iframe", ".nav", ".footer"],
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
    "risk_flag": "每个人物字段块另含长篇工作分工，只允许同组职务字段进入依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_adjacent_name_duty_fields",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom div.TRS_Editor p",
            "name_selector": "paragraph_name_field",
            "duty_selector": "next_nonempty_duty_field_before_next_name",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文已用姓名、职务和工作分工字段明确分组",
        },
        "migration": {
            "source": "legacy_inline_field_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_FIELD_PATTERN = re.compile(r"^姓名[：:]\s*(?P<name>[\u4e00-\u9fff·\s]{2,10})$")
DUTY_FIELD_PATTERN = re.compile(r"^职务[：:]\s*(?P<duty>.+)$")
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    normalized = " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", normalized)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名字段顺序配对同组紧邻职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(page_rule["leader_region_selector"])]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, paragraph in enumerate(paragraphs):
        name_match = NAME_FIELD_PATTERN.fullmatch(paragraph)
        if name_match is None:
            continue
        name = re.sub(r"\s+", "", name_match.group("name"))
        if NAME_PATTERN.fullmatch(name) is None or name in seen:
            continue
        evidence = ""
        for next_text in paragraphs[index + 1 : index + 4]:
            if NAME_FIELD_PATTERN.fullmatch(next_text):
                break
            duty_match = DUTY_FIELD_PATTERN.fullmatch(next_text)
            if duty_match is not None:
                evidence = clean_text(duty_match.group("duty"))
                break
        if not evidence or DUTY_HINT_PATTERN.search(evidence) is None:
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
                    "strategy=custom_parse_page；scope=#zoom_TRS_Editor；"
                    "name=name_field；duty=adjacent_duty_field_before_next_name；"
                    "responsibility_and_iframe=excluded"
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
