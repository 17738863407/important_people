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
    "rule_id": "2425",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_audit_bold_name_duty_headings_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_audit_bold_name_duty_headings_v1",
    "leader_region_selector": ".TRS_Editor b",
    "name_selector": "加粗标题内职务起始词之前的姓名",
    "duty_selector": "加粗标题内职务起始词及其后全文",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".TRS_Editor"],
        "exclude_selectors": ["工作分工", "个人简历", "iframe"],
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
    "risk_flag": "正文同时含领导加粗标题、工作分工和个人简历标签，姓名及职务间含不规则排版空格",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_bold_heading_name_duty_split",
    "locator": {
        "css": {
            "leader_region_selector": ".TRS_Editor b",
            "name_selector": "bold_text_before_first_duty_start",
            "duty_selector": "bold_text_from_first_duty_start",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文加粗标题直接提供姓名和当前职务",
        },
        "migration": {
            "source": "legacy_whole_editor_regex",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


DUTY_START_PATTERN = re.compile(r"党组|局长|长春市经济责任审计工作联席会议办公室主任")
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")


def compact_text(text: str) -> str:
    """移除HTML排版空白，不改变网页文字及标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按加粗领导标题顺序拆分姓名和原始职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for bold in soup.select(page_rule["leader_region_selector"]):
        heading = compact_text(bold.get_text("", strip=True))
        if heading in {"工作分工：", "个人简历："}:
            continue
        duty_match = DUTY_START_PATTERN.search(heading)
        if duty_match is None:
            continue
        name = heading[: duty_match.start()]
        evidence = heading[duty_match.start() :]
        if NAME_PATTERN.fullmatch(name) is None or not evidence or name in seen:
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
                    "strategy=custom_parse_page；scope=TRS_Editor_bold_headings；"
                    "name=before_duty_start；duty=from_duty_start；responsibility_and_biography=excluded"
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
