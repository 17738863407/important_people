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
    "rule_id": "0152",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_hrss_name_duty_span_paragraph_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_hrss_name_duty_span_paragraph_v1",
    "leader_region_selector": "div.neirong_content div.TRS_Editor p",
    "name_selector": "职务span之前的同段span",
    "duty_selector": "同段首个明确职务span及其后续span",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.neirong_content div.TRS_Editor"],
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
        "max_detail_links": 50,
    },
    "risk_flag": "人物职务段与分工段、空段交错；姓名可能被拆成多个相邻span",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_before_duty_span",
    "locator": {
        "css": {
            "leader_region_selector": "div.neirong_content div.TRS_Editor p",
            "name_selector": "same_paragraph_spans_before_duty",
            "duty_selector": "same_paragraph_spans_from_duty",
        },
        "api": {
            "enabled": False,
            "reason": "静态正文的人物段已用独立span明确区分姓名与职务",
        },
        "migration": {
            "source": "legacy_inline_paragraph_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINTS = ("党组", "局长", "主任", "书记", "成员")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def clean_name(text: str) -> str:
    """合并姓名因网页排版或多span拆分产生的空格。"""
    return clean_text(text).replace(" ", "")


def is_duty_text(text: str) -> bool:
    """判断当前强结构span是否为人物职务字段。"""
    return any(hint in text for hint in DUTY_HINTS)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析同段姓名和原始职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for paragraph in soup.select(page_rule["leader_region_selector"]):
        span_texts = [clean_text(node.get_text(" ", strip=True)) for node in paragraph.select("span")]
        span_texts = [text for text in span_texts if text]
        duty_index = next(
            (index for index, text in enumerate(span_texts) if is_duty_text(text)),
            None,
        )
        if duty_index is None or duty_index == 0:
            continue
        name = clean_name("".join(span_texts[:duty_index]))
        evidence = clean_text(" ".join(span_texts[duty_index:]))
        if NAME_PATTERN.fullmatch(name) is None or not evidence:
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
                    "name=same_paragraph_spans_before_duty；"
                    "duty=same_paragraph_duty_spans；responsibility_paragraphs=excluded"
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
