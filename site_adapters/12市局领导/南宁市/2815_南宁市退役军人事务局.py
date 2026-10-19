from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2815",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_veterans_division_notice_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_veterans_division_notice_v2",
    "leader_region_selector": "div.trs_editor_view, #UCAP-CONTENT",
    "name_selector": "姓名同志（或〔）职务标题段姓名",
    "duty_selector": "同一标题段完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "通知正文混有分工、收文单位和落款；只接受完整姓名同志括号职务标题段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "div.trs_editor_view, #UCAP-CONTENT", "name_selector": "姓名同志括号职务标题段", "duty_selector": "同一标题段完整原文"}, "api": {"enabled": False, "reason": "工作分工通知正文静态列出姓名和括号职务"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）〔〕])\s*", r"\1", value)


def parse_title(text: str) -> tuple[str, str]:
    value = normalize_layout(text)
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})同志(?:（(?P<round>.+)）|〔(?P<square>.+)〕)", value)
    if match is None:
        return "", ""
    duty = match.group("round") or match.group("square") or ""
    if re.search(r"(?:书记|局长|副局长|党组成员|调研员)", duty) is None:
        return "", ""
    return match.group("name"), duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.trs_editor_view, #UCAP-CONTENT")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, evidence = parse_title(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "通知正文姓名同志括号职务标题段按DOM顺序；保留同一段原文"})
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
