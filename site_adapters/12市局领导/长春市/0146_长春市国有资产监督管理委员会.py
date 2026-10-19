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
    "rule_id": "0146",
    "page_type": "多人物详情合并页",
    "structure_group": "changchun_sasac_bold_name_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_sasac_bold_name_current_sentence_v1",
    "leader_region_selector": "div.TRS_Editor div.Custom_UnionStyle > div",
    "name_selector": "b",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.TRS_Editor"],
        "exclude_selectors": [],
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
        "max_detail_links": 50,
    },
    "risk_flag": "人物简介块与工作分工块交替排列，必须以同块粗体姓名和现任句共同限定",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_bold_name_current_sentence",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor div.Custom_UnionStyle > div",
            "name_selector": "b",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文已经稳定包含人物姓名和完整现任职务原句",
        },
        "migration": {
            "source": "legacy_generic_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


CURRENT_DUTY_PATTERN = re.compile(r"现任[^。]*。")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取粗体姓名及同一人物块中的完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select(page_rule["leader_region_selector"]):
        name_node = block.select_one("b")
        if name_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        block_text = clean_text(block.get_text(" ", strip=True))
        duty_match = CURRENT_DUTY_PATTERN.search(block_text)
        if not name or duty_match is None or name in seen:
            continue
        evidence = re.sub(r"^现任\s*", "", clean_text(duty_match.group(0))).removesuffix("。").strip()
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=TRS_Editor direct_profile_blocks；"
                    "name=same_block_bold；duty=same_block_current_sentence；"
                    "responsibility_blocks=excluded"
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
