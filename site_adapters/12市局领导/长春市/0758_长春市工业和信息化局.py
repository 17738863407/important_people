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
    "rule_id": "0758",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_industry_bio_current_sentence_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_industry_bio_current_sentence_blocks_v1",
    "leader_region_selector": "div.text > div.TRS_Editor p",
    "name_selector": "人物基本信息段开头姓名",
    "duty_selector": "同一人物块中的完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.text > div.TRS_Editor"],
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
    "risk_flag": "人物块含历史履历和现任句后的分工；正文有嵌套同内容TRS_Editor",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_bio_block_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": "div.text > div.TRS_Editor p",
            "name_selector": "basic_profile_paragraph_prefix",
            "duty_selector": "same_profile_block_current_sentence",
        },
        "api": {
            "enabled": False,
            "reason": "静态合并正文已直接包含人物基本信息、历史履历和现任句",
        },
        "migration": {
            "source": "legacy_inline_combined_profile_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


BASIC_PROFILE_PATTERN = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,6})，(?:男|女)，")
CURRENT_DUTY_PATTERN = re.compile(r"现任\s*[^。]*。")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_current_evidence(text: str) -> str:
    """删除现任句的固定标签和纯句末句号，保留完整任职语义。"""
    cleaned = re.sub(r"^现任\s*", "", clean_text(text))
    return re.sub(r"。$", "", cleaned).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按基本信息段划分人物块，并提取块内完整现任原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [
        clean_text(node.get_text(" ", strip=True))
        for node in soup.select(page_rule["leader_region_selector"])
    ]
    profile_starts = [
        (index, match)
        for index, text in enumerate(paragraphs)
        if (match := BASIC_PROFILE_PATTERN.match(text)) is not None
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for order, (start_index, profile_match) in enumerate(profile_starts):
        end_index = profile_starts[order + 1][0] if order + 1 < len(profile_starts) else len(paragraphs)
        name = profile_match.group("name")
        block_text = clean_text(" ".join(paragraphs[start_index + 1 : end_index]))
        duty_match = CURRENT_DUTY_PATTERN.search(block_text)
        if duty_match is None or name in seen:
            continue
        evidence = clean_current_evidence(duty_match.group(0))
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=outer_TRS_Editor_profile_blocks；"
                    "name=basic_profile_prefix；duty=same_block_current_sentence；"
                    "history_responsibility_and_iframe=excluded"
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
