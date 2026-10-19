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
    "rule_id": "0154",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_transport_heading_bounded_profile_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_transport_heading_bounded_profile_v1",
    "leader_region_selector": "div.TRS_Editor p",
    "name_selector": "人物标题段开头姓名",
    "duty_selector": "当前人物区块中的完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
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
    "risk_flag": "人物区块含分工、联系单位和简历，页尾另有初审复审终审人员",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_heading_bounded_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor p",
            "name_selector": "profile_heading_prefix",
            "duty_selector": "same_profile_current_sentence",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文已按人物标题顺序包含各自完整现任句",
        },
        "migration": {
            "source": "legacy_inline_heading_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


HEADING_PATTERN = re.compile(
    r"^(?P<name>(?:[\u4e00-\u9fff·]\s*){2,6})\s+(?P<duty>[^。；;：:]{2,40})$"
)
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|副局长|主任|书记|调研员|纪检|总工程师")
CURRENT_DUTY_PATTERN = re.compile(r"现任[^。]*。")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def match_heading(text: str):
    """识别具有明确职务词的简短人物标题段。"""
    match = HEADING_PATTERN.fullmatch(text)
    if match is None or DUTY_HINT_PATTERN.search(match.group("duty")) is None:
        return None
    return match


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物标题划分正文区块，并提取区块内完整现任原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(page_rule["leader_region_selector"])]
    headings = [
        (index, match)
        for index, text in enumerate(paragraphs)
        if (match := match_heading(text)) is not None
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for heading_order, (start_index, heading) in enumerate(headings):
        end_index = headings[heading_order + 1][0] if heading_order + 1 < len(headings) else len(paragraphs)
        name = clean_name(heading.group("name"))
        block_text = clean_text(" ".join(paragraphs[start_index + 1 : end_index]))
        duty_match = CURRENT_DUTY_PATTERN.search(block_text)
        if not name or duty_match is None or name in seen:
            continue
        evidence = clean_text(duty_match.group(0))
        evidence = re.sub(r"^现任\s*", "", evidence).rstrip("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=TRS_Editor；"
                    "name=profile_heading_prefix；duty=before_next_heading_current_sentence；"
                    "responsibilities_and_reviewers=excluded"
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
