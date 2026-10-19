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
    "rule_id": "2809",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_veterans_bold_duty_name_headings_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_changchun_veterans_bold_duty_name_headings_v1",
    "leader_region_selector": "#zoom .TRS_Editor b, #zoom .TRS_Editor strong",
    "name_selector": "加粗标题末尾姓名",
    "duty_selector": "加粗标题中姓名之前的原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导成员",
        "end_anchor": "",
        "include_selectors": ["#zoom .TRS_Editor"],
        "exclude_selectors": ["工作分工", "个人简历", "履历正文", "iframe"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "同页每人均有工作分工与个人简历，领导标题和姓名含不规则排版空格；只解析非标签加粗标题",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_bold_duty_name_headings",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom .TRS_Editor b, #zoom .TRS_Editor strong",
            "name_selector": "heading_trailing_chinese_name",
            "duty_selector": "heading_prefix_before_name",
        },
        "api": {
            "enabled": False,
            "reason": "原始HTTP静态正文已直接提供职务和姓名，登录iframe不参与领导信息",
        },
        "migration": {
            "source": "legacy_body_text_work_division_lookback",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


HEADING_PATTERN = re.compile(
    r"^(?P<duty>局党组书记、局长|二级巡视员|局党组成员、副局长)"
    r"(?P<name>[\u4e00-\u9fff]{2,4})$"
)
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,4}")


def clean_text(text: str) -> str:
    """压缩HTML排版空白，不改变网页文字语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def compact_text(text: str) -> str:
    """移除标题中词内排版空白。"""
    return re.sub(r"\s+", "", clean_text(text))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按加粗领导标题顺序提取职务和姓名。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for bold in soup.select(page_rule["leader_region_selector"]):
        heading = clean_text(bold.get_text(" ", strip=True))
        if not heading or heading in {"工作分工", "个人简历"}:
            continue
        match = HEADING_PATTERN.fullmatch(compact_text(heading))
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
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
                "note": "strategy=custom_parse_page；scope=TRS_Editor_bold_headings；name=trailing_name；duty=heading_prefix；work_division_and_biography=excluded",
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
