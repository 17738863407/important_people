from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0204",
    "domain": "www.cgn-mca.ac.cn",
    "page_type": "人物表格页",
    "structure_group": "cgn_mca_adjacent_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_cgn_mca_adjacent_paragraphs_v1",
    "leader_region_selector": "div#right table.margintop10px",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "现任领导",
        "end_anchor": "",
        "include_selectors": ["div#right table.margintop10px"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "正文存在非法嵌套段落；姓名与职务分处相邻段落，职务机构前缀必须保留",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div#right table.margintop10px",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "现任领导",
                "end_anchor": "",
                "include_selectors": ["div#right table.margintop10px"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文已直接提供姓名和相邻职务段落",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白，不改变原始语义。"""
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"([、，；：])\s+", r"\1", text)


def is_name_paragraph(node: Tag, text: str) -> bool:
    """判断强标记段落是否只承载一个中文姓名。"""
    return bool(node.find("strong") and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", text) and text != "现任领导")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名段落顺序提取其后的完整原始职务段落。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div#right table.margintop10px")
    if not content:
        return []

    paragraphs = list(content.select("p"))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=div#right table.margintop10px；"
        "name=strong-only paragraph；duty=following non-empty paragraph"
    )

    for index, paragraph in enumerate(paragraphs):
        name = clean_text(paragraph.get_text(" ", strip=True))
        if name in seen or not is_name_paragraph(paragraph, name):
            continue

        evidence = ""
        for candidate in paragraphs[index + 1 : index + 5]:
            candidate_text = clean_text(candidate.get_text(" ", strip=True))
            if not candidate_text:
                continue
            if is_name_paragraph(candidate, candidate_text):
                break
            if "民政部地名研究所" in candidate_text:
                evidence = candidate_text
                break
        if not evidence:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
