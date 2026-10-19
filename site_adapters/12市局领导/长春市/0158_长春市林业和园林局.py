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
    "rule_id": "0158",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_forestry_name_duty_birth_paragraph_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_forestry_name_duty_birth_paragraph_v1",
    "leader_region_selector": "div.TRS_Editor p",
    "name_selector": "段首至首个逗号",
    "duty_selector": "首个逗号后至出生年月前的原始职务",
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
    "risk_flag": "人物段首含当前职务，后续长篇履历包含多条历史任职，必须以出生年月边界截断",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_duty_before_birth",
    "locator": {
        "css": {
            "leader_region_selector": "div.TRS_Editor p",
            "name_selector": "paragraph_prefix_before_first_comma",
            "duty_selector": "between_first_comma_and_birth_date",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文每个人物段首已明确给出姓名、当前职务和出生年月边界",
        },
        "migration": {
            "source": "legacy_inline_profile_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


PROFILE_START_PATTERN = re.compile(
    r"^(?P<name>[^，,]{2,8})[，,](?P<duty>.+?)[，,]\s*\d{4}年"
)
NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|纪检|组长")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版产生的字间空格。"""
    return clean_text(text).replace(" ", "")


def parse_profile_start(text: str) -> tuple[str, str]:
    """按段首姓名、职务和出生年月的强结构提取原始字段。"""
    match = PROFILE_START_PATTERN.search(clean_text(text))
    if match is None:
        return "", ""
    name = clean_name(match.group("name"))
    evidence = clean_text(match.group("duty"))
    if NAME_PATTERN.fullmatch(name) is None or DUTY_HINT_PATTERN.search(evidence) is None:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落原序提取人物段首姓名与完整原始职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for paragraph in soup.select(page_rule["leader_region_selector"]):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        name, evidence = parse_profile_start(paragraph_text)
        if not name or not evidence:
            continue
        key = (name, evidence)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；scope=TRS_Editor_paragraphs；"
                    "name=before_first_comma；duty=before_birth_date；"
                    "history_and_iframe=excluded"
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
