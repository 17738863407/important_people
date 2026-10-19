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
    "rule_id": "0968",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_ecology_profile_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_ecology_profile_current_sentence_v1",
    "leader_region_selector": "div.TRS_Editor p",
    "name_selector": "人物简历段开头姓名",
    "duty_selector": "同一简历段中的完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.TRS_Editor"],
        "exclude_selectors": ["iframe", ".footer"],
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
    "risk_flag": "简历段含大量曾任经历，正文外另有审校人员和页脚信息",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_same_paragraph_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor p",
            "name_selector": "profile_paragraph_prefix",
            "duty_selector": "same_paragraph_current_sentence",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文每个人物简历段均直接包含姓名和完整现任句",
        },
        "migration": {
            "source": "legacy_inline_profile_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


PROFILE_NAME_PATTERN = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,6})，")
CURRENT_DUTY_PATTERN = re.compile(r"现任[^。]*。")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_current_evidence(text: str) -> str:
    """删除现任句固定标签和纯句末句号，保留完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(text))
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简历段顺序提取段首姓名和同段完整现任原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(page_rule["leader_region_selector"]):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = PROFILE_NAME_PATTERN.match(paragraph_text)
        duty_match = CURRENT_DUTY_PATTERN.search(paragraph_text)
        if name_match is None or duty_match is None:
            continue
        name = name_match.group("name")
        evidence = clean_current_evidence(duty_match.group(0))
        if name in seen:
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
                    "strategy=custom_parse_page；scope=TRS_Editor_profile_paragraphs；"
                    "name=paragraph_prefix；duty=same_paragraph_current_sentence；"
                    "history_reviewers_and_footer=excluded"
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
